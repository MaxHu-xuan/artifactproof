# SPDX-License-Identifier: Apache-2.0

"""Receipt creation, signing, persistence and verification."""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Sequence, Tuple, Union

from .errors import (
    ArtifactChangedError,
    InputError,
    QualityCheckError,
    ReceiptFormatError,
    SigningKeyError,
    VerificationError,
)
from .hashing import FileDigest, PathLike, digest_file
from .pptx import PptxQAResult, inspect_pptx


SCHEMA_VERSION = "artifactproof.receipt.v1"
SIGNATURE_ALGORITHM = "HMAC-SHA256"
MIN_KEY_BYTES = 32
MAX_RECEIPT_BYTES = 1024 * 1024
KEY_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
CODE_RE = re.compile(r"^[a-z0-9_.-]{1,64}$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
CANONICAL_UTC_TIMESTAMP_RE = re.compile(
    r"^(?P<base>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})"
    r"(?:\.[0-9]+)?Z$"
)


def _key_bytes(signing_key: Union[str, bytes, bytearray]) -> bytes:
    if isinstance(signing_key, str):
        key = signing_key.encode("utf-8")
    elif isinstance(signing_key, (bytes, bytearray)):
        key = bytes(signing_key)
    else:
        raise SigningKeyError()
    if len(key) < MIN_KEY_BYTES:
        raise SigningKeyError()
    return key


def parse_signing_key(value: str) -> bytes:
    """Parse an environment value without ever returning it in an error."""

    if not isinstance(value, str):
        raise SigningKeyError()
    try:
        if value.startswith("base64:"):
            key = base64.b64decode(value[7:].encode("ascii"), validate=True)
        elif value.startswith("hex:"):
            key = bytes.fromhex(value[4:])
        else:
            key = value.encode("utf-8")
    except (UnicodeError, ValueError, binascii.Error) as exc:
        raise SigningKeyError() from exc
    return _key_bytes(key)


def signing_key_from_env(name: str, environ: Optional[Mapping[str, str]] = None) -> bytes:
    if not ENV_NAME_RE.fullmatch(name or ""):
        raise SigningKeyError()
    source = os.environ if environ is None else environ
    value = source.get(name)
    if value is None:
        raise SigningKeyError()
    return parse_signing_key(value)


def _canonical_payload(receipt: Mapping[str, object]) -> bytes:
    payload = copy.deepcopy(dict(receipt))
    signature = payload.get("signature")
    if not isinstance(signature, dict):
        raise ReceiptFormatError()
    signature.pop("value", None)
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ReceiptFormatError() from exc


def _signature_value(receipt: Mapping[str, object], signing_key: Union[str, bytes]) -> str:
    key = _key_bytes(signing_key)
    return hmac.new(key, _canonical_payload(receipt), hashlib.sha256).hexdigest()


def _valid_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 255
        and not any(
            ord(character) < 32
            or ord(character) == 127
            or 0xD800 <= ord(character) <= 0xDFFF
            for character in value
        )
    )


def _valid_digest(item: object) -> bool:
    if not isinstance(item, dict) or set(item) != {"name", "sha256", "size_bytes"}:
        return False
    size = item.get("size_bytes")
    return (
        _valid_name(item.get("name"))
        and isinstance(item.get("sha256"), str)
        and SHA256_RE.fullmatch(item["sha256"]) is not None
        and isinstance(size, int)
        and not isinstance(size, bool)
        and size >= 0
    )


def _valid_check(item: object) -> bool:
    if not isinstance(item, dict) or not {"id", "status"}.issubset(item):
        return False
    if not set(item).issubset({"id", "status", "detail"}):
        return False
    detail = item.get("detail")
    return (
        isinstance(item.get("id"), str)
        and CODE_RE.fullmatch(item["id"]) is not None
        and item.get("status") in ("pass", "fail")
        and (detail is None or (isinstance(detail, str) and len(detail) <= 256))
    )


def _validate_receipt(receipt: object) -> Dict[str, object]:
    if not isinstance(receipt, dict):
        raise ReceiptFormatError()
    expected = {"schema_version", "created_at", "artifact", "evidence", "qa", "signature"}
    if set(receipt) != expected or receipt.get("schema_version") != SCHEMA_VERSION:
        raise ReceiptFormatError()

    created_at = receipt.get("created_at")
    timestamp_match = (
        CANONICAL_UTC_TIMESTAMP_RE.fullmatch(created_at)
        if isinstance(created_at, str)
        else None
    )
    if timestamp_match is None:
        raise ReceiptFormatError()
    try:
        datetime.strptime(timestamp_match.group("base"), "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ReceiptFormatError() from exc

    if not _valid_digest(receipt.get("artifact")):
        raise ReceiptFormatError()
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or not all(_valid_digest(item) for item in evidence):
        raise ReceiptFormatError()
    evidence_names = [item["name"] for item in evidence]
    if len(evidence_names) != len(set(evidence_names)):
        raise ReceiptFormatError()

    qa = receipt.get("qa")
    if not isinstance(qa, dict) or set(qa) != {
        "kind",
        "passed",
        "slide_count",
        "checks",
        "errors",
        "warnings",
    }:
        raise ReceiptFormatError()
    slide_count = qa.get("slide_count")
    if (
        qa.get("kind") != "pptx-basic"
        or qa.get("passed") is not True
        or not isinstance(slide_count, int)
        or isinstance(slide_count, bool)
        or slide_count < 1
    ):
        raise ReceiptFormatError()
    checks = qa.get("checks")
    errors = qa.get("errors")
    warnings = qa.get("warnings")
    if not isinstance(checks, list) or not checks or not all(_valid_check(item) for item in checks):
        raise ReceiptFormatError()
    for values in (errors, warnings):
        if not isinstance(values, list) or not all(
            isinstance(code, str) and CODE_RE.fullmatch(code) is not None for code in values
        ):
            raise ReceiptFormatError()
    if errors or any(item["status"] != "pass" for item in checks):
        raise ReceiptFormatError()

    signature = receipt.get("signature")
    if not isinstance(signature, dict) or set(signature) != {"algorithm", "key_id", "value"}:
        raise ReceiptFormatError()
    if (
        signature.get("algorithm") != SIGNATURE_ALGORITHM
        or not isinstance(signature.get("key_id"), str)
        or KEY_ID_RE.fullmatch(signature["key_id"]) is None
        or not isinstance(signature.get("value"), str)
        or SHA256_RE.fullmatch(signature["value"]) is None
    ):
        raise ReceiptFormatError()
    return receipt


def create_receipt(
    artifact: PathLike,
    evidence: Optional[Mapping[str, PathLike]],
    signing_key: Union[str, bytes, bytearray],
    key_id: str,
    qa_runner: Callable[[PathLike], PptxQAResult] = inspect_pptx,
) -> Dict[str, object]:
    """Create a signed receipt, failing if QA or stability checks fail."""

    if not isinstance(key_id, str) or KEY_ID_RE.fullmatch(key_id) is None:
        raise SigningKeyError("the key identifier is invalid")
    key = _key_bytes(signing_key)
    artifact_before = digest_file(artifact)
    try:
        qa_result = qa_runner(artifact)
    except Exception as exc:
        if isinstance(exc, ArtifactChangedError):
            raise
        raise QualityCheckError(("pptx.qa_runtime_error",)) from exc
    artifact_after = digest_file(artifact)
    if artifact_before != artifact_after:
        raise ArtifactChangedError()
    if not isinstance(qa_result, PptxQAResult):
        raise QualityCheckError(("pptx.qa_result_invalid",))
    if not qa_result.passed:
        raise QualityCheckError(qa_result.errors)

    evidence_items = list((evidence or {}).items())
    if not all(isinstance(name, str) for name, _ in evidence_items):
        raise InputError("an evidence name is invalid")
    evidence_before = {
        name: digest_file(path, name=name)
        for name, path in sorted(evidence_items, key=lambda item: item[0])
    }

    artifact_final = digest_file(artifact)
    if artifact_after != artifact_final:
        raise ArtifactChangedError()
    evidence_final = {
        name: digest_file(path, name=name)
        for name, path in sorted(evidence_items, key=lambda item: item[0])
    }
    if evidence_before != evidence_final:
        raise ArtifactChangedError()

    receipt: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifact": artifact_final.to_dict(),
        "evidence": [evidence_final[name].to_dict() for name in sorted(evidence_final)],
        "qa": qa_result.to_dict(),
        "signature": {
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id": key_id,
            "value": "",
        },
    }
    receipt["signature"]["value"] = _signature_value(receipt, key)
    artifact_at_return = digest_file(artifact)
    if artifact_final != artifact_at_return:
        raise ArtifactChangedError()
    evidence_at_return = {
        name: digest_file(path, name=name)
        for name, path in sorted(evidence_items, key=lambda item: item[0])
    }
    if evidence_final != evidence_at_return:
        raise ArtifactChangedError()
    return _validate_receipt(receipt)


def verify_receipt(
    receipt: object,
    artifact: PathLike,
    evidence: Optional[Mapping[str, PathLike]],
    signing_key: Union[str, bytes, bytearray],
    expected_key_id: Optional[str] = None,
) -> bool:
    """Verify signature first, then the exact artifact and evidence digests."""

    validated = _validate_receipt(receipt)
    key = _key_bytes(signing_key)
    signature = validated["signature"]
    if expected_key_id is not None and signature["key_id"] != expected_key_id:
        raise VerificationError()
    expected_signature = _signature_value(validated, key)
    if not hmac.compare_digest(signature["value"], expected_signature):
        raise VerificationError()

    artifact_digest = digest_file(artifact)
    recorded_artifact = validated["artifact"]
    if (
        artifact_digest.sha256 != recorded_artifact["sha256"]
        or artifact_digest.size_bytes != recorded_artifact["size_bytes"]
    ):
        raise VerificationError()

    supplied = dict(evidence or {})
    recorded_evidence = validated["evidence"]
    recorded_names = {item["name"] for item in recorded_evidence}
    if set(supplied) != recorded_names:
        raise VerificationError()
    evidence_digests = {}
    for item in recorded_evidence:
        actual = digest_file(supplied[item["name"]], name=item["name"])
        if actual.sha256 != item["sha256"] or actual.size_bytes != item["size_bytes"]:
            raise VerificationError()
        evidence_digests[item["name"]] = actual
    artifact_digest_after = digest_file(artifact)
    if artifact_digest_after != artifact_digest:
        raise ArtifactChangedError()
    evidence_digests_after = {
        name: digest_file(path, name=name) for name, path in sorted(supplied.items())
    }
    if evidence_digests_after != evidence_digests:
        raise ArtifactChangedError()
    return True


def _paths_alias(first: PathLike, second: PathLike) -> bool:
    first_path = Path(first)
    second_path = Path(second)
    try:
        if first_path.resolve(strict=False) == second_path.resolve(strict=False):
            return True
        if os.path.lexists(str(first_path)) and os.path.lexists(str(second_path)):
            return os.path.samefile(str(first_path), str(second_path))
    except (OSError, RuntimeError, ValueError) as exc:
        raise InputError("file identity could not be checked safely") from exc
    return False


def _assert_destination_safe(
    destination: PathLike, protected_paths: Sequence[PathLike]
) -> None:
    for protected in protected_paths:
        if _paths_alias(destination, protected):
            raise InputError("the receipt destination aliases a protected input")


def write_receipt(
    path: PathLike,
    receipt: object,
    protected_paths: Sequence[PathLike],
) -> None:
    """Atomically write a validated receipt with restrictive local permissions."""

    validated = _validate_receipt(receipt)
    destination = Path(path)
    _assert_destination_safe(destination, protected_paths)
    parent = destination.parent
    if not parent.is_dir():
        raise InputError("the receipt destination directory does not exist")
    temporary_name = None
    descriptor = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".artifactproof-", suffix=".tmp", dir=str(parent)
        )
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            descriptor = None
            json.dump(validated, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        _assert_destination_safe(destination, protected_paths)
        os.replace(temporary_name, destination)
        temporary_name = None
    except OSError as exc:
        raise InputError("the receipt could not be written") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass


def _receipt_file_identity(metadata: os.stat_result) -> Tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _read_receipt_bytes(path: Path) -> bytes:
    descriptor = None
    try:
        path_before = path.stat()
        if (
            not stat.S_ISREG(path_before.st_mode)
            or path_before.st_size > MAX_RECEIPT_BYTES
        ):
            raise ReceiptFormatError()
        flags = os.O_RDONLY
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY
        descriptor = os.open(str(path), flags)
        descriptor_before = os.fstat(descriptor)
        if _receipt_file_identity(path_before) != _receipt_file_identity(
            descriptor_before
        ):
            raise ReceiptFormatError()
        chunks = []
        total = 0
        while total <= MAX_RECEIPT_BYTES:
            block = os.read(
                descriptor,
                min(64 * 1024, MAX_RECEIPT_BYTES + 1 - total),
            )
            if not block:
                break
            chunks.append(block)
            total += len(block)
        descriptor_after = os.fstat(descriptor)
        path_after = path.stat()
    except ReceiptFormatError:
        raise
    except (OSError, ValueError) as exc:
        raise ReceiptFormatError() from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    if (
        total > MAX_RECEIPT_BYTES
        or _receipt_file_identity(descriptor_before)
        != _receipt_file_identity(descriptor_after)
        or _receipt_file_identity(descriptor_after)
        != _receipt_file_identity(path_after)
    ):
        raise ReceiptFormatError()
    return b"".join(chunks)


def load_receipt(path: PathLike) -> Dict[str, object]:
    receipt_path = Path(path)
    try:
        content = _read_receipt_bytes(receipt_path).decode("utf-8")
        receipt = json.loads(content, object_pairs_hook=_object_without_duplicates)
    except ReceiptFormatError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReceiptFormatError() from exc
    return _validate_receipt(receipt)


def _object_without_duplicates(pairs: Sequence[Tuple[str, object]]) -> Dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptFormatError()
        result[key] = value
    return result
