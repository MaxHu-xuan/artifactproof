#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Values-free pre-publication audit for the ArtifactProof release tree."""

from __future__ import annotations

import argparse
import collections
import errno
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Counter, Dict, Iterator, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_LICENSE_SHA256 = "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4"
MAX_FILE_BYTES = 1_048_576
SKIP_DIRS = frozenset((".git",))
SDIST_EGG_INFO = "src/artifactproof.egg-info"
RESIDUE_DIRS = frozenset(
    (".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv", "__pycache__", "build", "dist")
)
DATA_SUFFIXES = frozenset(
    (
        ".avro", ".csv", ".db", ".docx", ".eml", ".gif", ".gz", ".har",
        ".jpeg", ".jpg", ".jsonl", ".key", ".log", ".mbox", ".msg",
        ".ndjson", ".p12", ".parquet", ".pcap", ".pdf", ".pem", ".pfx",
        ".png", ".ppt", ".pptx", ".pyc", ".sqlite", ".sqlite3", ".tsv",
        ".webp", ".whl", ".zip",
    )
)
FORBIDDEN_NAMES = frozenset((".env", ".DS_Store", "credentials.json", "secrets.json"))
TEXT_SUFFIXES = frozenset(
    ("", ".cfg", ".in", ".ini", ".json", ".md", ".py", ".rst", ".toml", ".txt", ".yaml", ".yml")
)
TEXT_NAMES = frozenset((".gitignore", "LICENSE", "MANIFEST.in"))
REQUIRED_FILES = (
    "CHANGELOG.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "LICENSE",
    "MANIFEST.in", "PROVENANCE.md", "README.md", "RELEASING.md",
    "SECURITY.md", "SUPPORT.md", "THREAT_MODEL.md", "pyproject.toml",
    "scripts/canonicalize_sdist.py", "scripts/privacy_audit.py",
)


def _joined(*parts: str) -> str:
    return "".join(parts)


CONTENT_PATTERNS: Sequence[Tuple[str, re.Pattern]] = (
    ("source.absolute_home_path", re.compile(_joined(r"/(?:", "Users", r"|home)/[^/\s]+/"))),
    (
        "source.absolute_home_path",
        re.compile(
            _joined(
                r"(?i)\b[A-Z]:[\\/](?:",
                "Users",
                r"|Documents and Settings)[\\/][^\\/\s]+[\\/]",
            )
        ),
    ),
    ("source.privileged_home_path", re.compile(_joined(r"/", "root", r"/"))),
    ("source.email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("source.phone_number", re.compile(r"(?<![A-Za-z0-9])(?:\+?\d[ -]?){10,15}(?![A-Za-z0-9])")),
    ("source.ipv4_address", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")),
    (
        "source.provider_key",
        re.compile(_joined(r"(?<![A-Za-z0-9])(?:", "s", r"k-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{12,}|gh[pousr]_[A-Za-z0-9]{20,})(?![A-Za-z0-9])")),
    ),
    ("source.private_key", re.compile(_joined(r"-----BEGIN ", r"(?:RSA |EC |OPENSSH )?", "PRIVATE KEY", r"-----"))),
    (
        "source.credential_assignment",
        re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
    ),
)


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _files(
    root: Path,
    findings: Counter[Tuple[str, str]],
    sdist: bool = False,
) -> Iterator[Path]:
    def on_walk_error(error: OSError) -> None:
        raw_path = getattr(error, "filename", None)
        relative = "."
        if isinstance(raw_path, str):
            try:
                candidate = Path(raw_path)
                candidate_relative = candidate.relative_to(root)
                if all(part not in ("", ".", "..") for part in candidate_relative.parts):
                    relative = candidate_relative.as_posix()
            except (OSError, ValueError):
                pass
        findings[(relative, "scan.directory_error")] += 1

    for directory, names, files in os.walk(
        str(root),
        topdown=True,
        onerror=on_walk_error,
        followlinks=False,
    ):
        base = Path(directory)
        kept = []
        for name in sorted(names):
            candidate = base / name
            relative = _relative(candidate, root)
            if candidate.is_symlink():
                findings[(relative, "artifact.symlink")] += 1
            elif name in RESIDUE_DIRS:
                findings[(relative, "artifact.generated_directory")] += 1
            elif name.endswith(".egg-info"):
                if sdist and relative == SDIST_EGG_INFO:
                    kept.append(name)
                else:
                    findings[(relative, "artifact.generated_directory")] += 1
            elif name not in SKIP_DIRS:
                kept.append(name)
        names[:] = kept
        for name in sorted(files):
            yield base / name


def _metadata_checks(root: Path, findings: Counter[Tuple[str, str]]) -> None:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            findings[(relative, "release.required_file_missing")] += 1

    license_path = root / "LICENSE"
    try:
        license_bytes = license_path.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        return
    if hashlib.sha256(license_bytes).hexdigest() != EXPECTED_LICENSE_SHA256:
        findings[("LICENSE", "license.apache_2_0_mismatch")] += 1

    try:
        metadata = (root / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return
    checks = (
        (r"(?m)^license\s*=\s*['\"]Apache-2\.0['\"]\s*$", "metadata.license_expression_missing"),
        (r"(?m)^license-files\s*=\s*\[\s*['\"]LICENSE['\"]\s*\]\s*$", "metadata.license_file_missing"),
        (r"(?m)^dependencies\s*=\s*\[\s*\]\s*$", "metadata.runtime_dependencies_present"),
        (r"setuptools>=77\.0\.3", "metadata.build_backend_too_old"),
    )
    for pattern, code in checks:
        if not re.search(pattern, metadata):
            findings[(("pyproject.toml"), code)] += 1

    try:
        manifest = (root / "MANIFEST.in").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return
    for entry in (
        "include LICENSE",
        "include scripts/canonicalize_sdist.py",
        "include scripts/privacy_audit.py",
    ):
        if entry not in manifest.splitlines():
            findings[("MANIFEST.in", "metadata.sdist_entry_missing")] += 1


def audit(
    root: Path,
    validate_release: bool = True,
    sdist: bool = False,
) -> Dict[str, object]:
    findings: Counter[Tuple[str, str]] = collections.Counter()
    files_scanned = 0
    try:
        if root.is_symlink() or not root.is_dir():
            findings[(".", "scan.invalid_root")] += 1
            return _report(findings, files_scanned)
        root = root.resolve()
    except OSError:
        findings[(".", "scan.invalid_root")] += 1
        return _report(findings, files_scanned)

    if validate_release:
        _metadata_checks(root, findings)

    for path in _files(root, findings, sdist=sdist):
        relative = _relative(path, root)
        try:
            metadata = path.lstat()
        except OSError:
            findings[(relative, "scan.metadata_error")] += 1
            continue
        if stat.S_ISLNK(metadata.st_mode):
            findings[(relative, "artifact.symlink")] += 1
            continue
        if not stat.S_ISREG(metadata.st_mode):
            findings[(relative, "artifact.non_regular")] += 1
            continue
        if metadata.st_nlink != 1:
            findings[(relative, "artifact.hardlink")] += 1
        files_scanned += 1
        if path.name in FORBIDDEN_NAMES:
            findings[(relative, "artifact.forbidden_name")] += 1
        if path.suffix.lower() in DATA_SUFFIXES:
            findings[(relative, "artifact.persistent_data")] += 1
            continue
        if metadata.st_size > MAX_FILE_BYTES:
            findings[(relative, "artifact.oversized")] += 1
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            findings[(relative, "artifact.binary_or_unknown")] += 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError):
            findings[(relative, "scan.text_error")] += 1
            continue
        for code, pattern in CONTENT_PATTERNS:
            count = sum(1 for _ in pattern.finditer(text))
            if count:
                findings[(relative, code)] += count
        if path.suffix.lower() == ".py":
            if "# SPDX-License-Identifier: Apache-2.0" not in text.splitlines()[:5]:
                findings[(relative, "license.spdx_missing")] += 1
    return _report(findings, files_scanned)


def _report(findings: Counter[Tuple[str, str]], files_scanned: int) -> Dict[str, object]:
    rows = [
        {"path": path, "code": code, "count": count}
        for (path, code), count in sorted(findings.items())
    ]
    return {
        "schema": "artifactproof-privacy-audit-v1",
        "ok": not rows,
        "files_scanned": files_scanned,
        "finding_count": sum(row["count"] for row in rows),
        "findings": rows,
    }


def self_test(root: Path = PROJECT_ROOT, sdist: bool = False) -> bool:
    if not audit(root, sdist=sdist)["ok"]:
        return False
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        values = (
            "/ho" + "me/" + "sample-user/notes",
            "C:" + "\\Us" + "ers\\" + "sample-user\\notes",
            "person" + "@" + "example.invalid",
            "139" + "\u0660" * 4 + "\u0661" * 4,
            "192" + ".0.2.1",
            "s" + "k-" + "A" * 24,
            "-----BEGIN " + "PRIVATE KEY-----",
            "pass" + "word = 'synthetic-value'",
        )
        (root / "sample.txt").write_text("\n".join(values), encoding="utf-8")
        (root / "fixture.db").write_bytes(b"synthetic")
        report = audit(root, validate_release=False)
        codes = {row["code"] for row in report["findings"]}
        expected = {
            "artifact.persistent_data", "source.absolute_home_path",
            "source.credential_assignment", "source.email_address",
            "source.ipv4_address", "source.phone_number", "source.private_key",
            "source.provider_key",
        }
        encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
        if not expected.issubset(codes) or any(value in encoded for value in values):
            return False

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        exact = root / SDIST_EGG_INFO
        exact.mkdir(parents=True)
        metadata_path = exact / "PKG-INFO"
        metadata_path.write_text(
            "Metadata-Version: 2.4\nName: artifactproof\n",
            encoding="utf-8",
        )

        source_report = audit(root, validate_release=False)
        if source_report["ok"] or not _has_finding(
            source_report,
            SDIST_EGG_INFO,
            "artifact.generated_directory",
        ):
            return False

        sdist_report = audit(root, validate_release=False, sdist=True)
        if not sdist_report["ok"] or sdist_report["files_scanned"] != 1:
            return False

        private_value = "person" + "@" + "example.invalid"
        metadata_path.write_text(private_value, encoding="utf-8")
        scanned_report = audit(root, validate_release=False, sdist=True)
        scanned_encoded = json.dumps(
            scanned_report,
            sort_keys=True,
            separators=(",", ":"),
        )
        if not _has_finding(
            scanned_report,
            SDIST_EGG_INFO + "/PKG-INFO",
            "source.email_address",
        ) or private_value in scanned_encoded:
            return False

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        impostor = root / "src" / "artifactproof-copy.egg-info"
        impostor.mkdir(parents=True)
        impostor_report = audit(root, validate_release=False, sdist=True)
        if impostor_report["ok"] or not _has_finding(
            impostor_report,
            "src/artifactproof-copy.egg-info",
            "artifact.generated_directory",
        ):
            return False

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / SDIST_EGG_INFO).mkdir(parents=True)
        extra_egg_info = root / "src" / "other.egg-info"
        extra_egg_info.mkdir(parents=True)
        (root / "build").mkdir()
        extra_report = audit(root, validate_release=False, sdist=True)
        if extra_report["ok"]:
            return False
        for relative in ("src/other.egg-info", "build"):
            if not _has_finding(
                extra_report,
                relative,
                "artifact.generated_directory",
            ):
                return False

    with tempfile.TemporaryDirectory() as directory:
        synthetic_root = Path(directory).resolve()
        original_walk = os.walk

        def denied_walk(*args, **kwargs):
            del args
            onerror = kwargs.get("onerror")
            if onerror is not None:
                onerror(
                    OSError(
                        errno.EACCES,
                        "synthetic directory error",
                        str(synthetic_root / "blocked"),
                    )
                )
            return iter(())

        os.walk = denied_walk
        try:
            unreadable_report = audit(synthetic_root, validate_release=False)
        finally:
            os.walk = original_walk
        if unreadable_report["ok"] or not _has_finding(
            unreadable_report,
            "blocked",
            "scan.directory_error",
        ):
            return False
    return True


def _has_finding(report: Dict[str, object], path: str, code: str) -> bool:
    return any(
        row.get("path") == path and row.get("code") == code
        for row in report.get("findings", ())
    )


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("invalid arguments")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = SafeArgumentParser(description="Audit a release tree without echoing values")
    parser.add_argument("root", nargs="?", default=str(PROJECT_ROOT))
    parser.add_argument(
        "--sdist",
        action="store_true",
        help="allow and scan only the expected sdist-generated egg-info directory",
    )
    parser.add_argument("--self-test", action="store_true")
    try:
        args = parser.parse_args(argv)
        if args.self_test:
            ok = self_test(root=Path(args.root), sdist=args.sdist)
            print(json.dumps({"ok": ok, "code": "ok" if ok else "self_test_failed", "count": 0 if ok else 1}, sort_keys=True, separators=(",", ":")))
            return 0 if ok else 1
        report = audit(Path(args.root), sdist=args.sdist)
    except (OSError, ValueError):
        report = {"ok": False, "finding_count": 1, "findings": [{"path": ".", "code": "scan.invalid_arguments", "count": 1}]}
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
