# SPDX-License-Identifier: Apache-2.0

"""Command-line interface with intentionally non-sensitive output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .errors import ArtifactProofError, InputError
from .receipt import (
    create_receipt,
    load_receipt,
    signing_key_from_env,
    verify_receipt,
    write_receipt,
)


DEFAULT_KEY_ENV = "ARTIFACTPROOF_SIGNING_KEY"


class SafeArgumentParser(argparse.ArgumentParser):
    """Argparse variant that never echoes untrusted argument values."""

    def error(self, message):
        raise InputError("command-line arguments are invalid")


def _evidence_map(values: Sequence[str]) -> Dict[str, Path]:
    evidence: Dict[str, Path] = {}
    for value in values:
        if "=" in value:
            name, raw_path = value.split("=", 1)
        else:
            raw_path = value
            name = Path(value).name
        if not name or not raw_path or name in evidence:
            raise InputError("an evidence argument is invalid or duplicated")
        evidence[name] = Path(raw_path)
    return evidence


def _parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(
        prog="artifactproof",
        description="Create and verify offline, hash-bound artifact QA receipts.",
    )
    parser.add_argument("--version", action="version", version="artifactproof 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="QA an artifact and create a receipt")
    create.add_argument("artifact")
    create.add_argument("--receipt", required=True)
    create.add_argument("--evidence", action="append", default=[], metavar="NAME=PATH")
    create.add_argument("--key-env", default=DEFAULT_KEY_ENV, metavar="ENV_NAME")
    create.add_argument("--key-id", default="default")

    verify = subparsers.add_parser("verify", help="verify a receipt and bound files")
    verify.add_argument("artifact")
    verify.add_argument("--receipt", required=True)
    verify.add_argument("--evidence", action="append", default=[], metavar="NAME=PATH")
    verify.add_argument("--key-env", default=DEFAULT_KEY_ENV, metavar="ENV_NAME")
    verify.add_argument("--expected-key-id")
    return parser


def _emit(payload: Dict[str, object], stream) -> None:
    stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = _parser().parse_args(argv)
        key = signing_key_from_env(args.key_env)
        evidence = _evidence_map(args.evidence)
        if args.command == "create":
            receipt = create_receipt(
                Path(args.artifact),
                evidence=evidence,
                signing_key=key,
                key_id=args.key_id,
            )
            write_receipt(
                Path(args.receipt),
                receipt,
                protected_paths=[Path(args.artifact)] + list(evidence.values()),
            )
            _emit(
                {
                    "ok": True,
                    "operation": "create",
                    "qa": "pass",
                    "receipt_written": True,
                },
                sys.stdout,
            )
            return 0
        if args.command == "verify":
            receipt = load_receipt(Path(args.receipt))
            verify_receipt(
                receipt,
                Path(args.artifact),
                evidence=evidence,
                signing_key=key,
                expected_key_id=args.expected_key_id,
            )
            _emit({"ok": True, "operation": "verify", "verified": True}, sys.stdout)
            return 0
        raise InputError("an unsupported operation was requested")
    except ArtifactProofError as exc:
        _emit({"error": exc.code, "message": str(exc), "ok": False}, sys.stderr)
        return 2
    except Exception:
        _emit(
            {
                "error": "internal_error",
                "message": "an unexpected internal error occurred",
                "ok": False,
            },
            sys.stderr,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
