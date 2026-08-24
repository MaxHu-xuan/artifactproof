#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Run the ArtifactProof CLI against temporary, fully synthetic inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Mapping, Tuple


_PREVIOUS_DONT_WRITE_BYTECODE = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    from generate_demo import (
        DemoGenerationError,
        EVIDENCE_NAME,
        PPTX_NAME,
        generate_demo,
    )
finally:
    sys.dont_write_bytecode = _PREVIOUS_DONT_WRITE_BYTECODE
del _PREVIOUS_DONT_WRITE_BYTECODE


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"
DEMO_KEY = "ARTIFACTPROOF_DEMO_KEY_NOT_A_SECRET_0001"
RECEIPT_NAME = "synthetic-deck.receipt.json"
COMMAND_TIMEOUT_SECONDS = 30
PLATFORM_ENVIRONMENT_NAMES = (
    "COMSPEC",
    "LANG",
    "LC_ALL",
    "PATH",
    "PATHEXT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
)


def _environment() -> Mapping[str, str]:
    environment = {
        name: os.environ[name]
        for name in PLATFORM_ENVIRONMENT_NAMES
        if name in os.environ
    }
    environment["PYTHONPATH"] = str(SOURCE_ROOT)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONUTF8"] = "1"
    environment["ARTIFACTPROOF_SIGNING_KEY"] = DEMO_KEY
    return environment


def _run_cli(arguments: List[str]) -> Tuple[int, str, str]:
    process = subprocess.run(
        [sys.executable, "-m", "artifactproof", *arguments],
        cwd=str(PROJECT_ROOT),
        env=_environment(),
        check=False,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    return process.returncode, process.stdout.strip(), process.stderr.strip()


def _emit(payload: Mapping[str, object], stream=sys.stdout) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=stream)


def _forward_success(result: Tuple[int, str, str], operation: str) -> bool:
    status, stdout, stderr = result
    if status != 0 or stderr:
        _emit({"error": "demo_command_failed", "ok": False, "operation": operation}, sys.stderr)
        return False
    try:
        payload = json.loads(stdout)
    except (TypeError, ValueError):
        _emit({"error": "demo_output_invalid", "ok": False, "operation": operation}, sys.stderr)
        return False
    if payload.get("ok") is not True or payload.get("operation") != operation:
        _emit({"error": "demo_output_invalid", "ok": False, "operation": operation}, sys.stderr)
        return False
    print(stdout)
    return True


def _run_demo() -> int:
    with tempfile.TemporaryDirectory(prefix="artifactproof-synthetic-demo-") as directory:
        root = Path(directory)
        artifact, evidence = generate_demo(root)
        receipt = root / RECEIPT_NAME
        _emit(
            {
                "evidence": EVIDENCE_NAME,
                "ok": True,
                "operation": "generate",
                "pptx": PPTX_NAME,
            }
        )

        create = _run_cli(
            [
                "create",
                str(artifact),
                "--artifact-name",
                PPTX_NAME,
                "--evidence",
                "review=" + str(evidence),
                "--receipt",
                str(receipt),
                "--key-id",
                "demo-local",
            ]
        )
        if not _forward_success(create, "create"):
            return 1

        verify_arguments = [
            "verify",
            str(artifact),
            "--evidence",
            "review=" + str(evidence),
            "--receipt",
            str(receipt),
            "--expected-key-id",
            "demo-local",
        ]
        if not _forward_success(_run_cli(verify_arguments), "verify"):
            return 1

        with artifact.open("ab") as stream:
            stream.write(b"artifactproof-synthetic-tamper")
        status, stdout, stderr = _run_cli(verify_arguments)
        if status != 2 or stdout:
            _emit({"error": "tamper_check_failed", "ok": False}, sys.stderr)
            return 1
        try:
            failure = json.loads(stderr)
        except (TypeError, ValueError):
            _emit({"error": "tamper_check_failed", "ok": False}, sys.stderr)
            return 1
        if failure.get("ok") is not False or failure.get("error") != "verification_failed":
            _emit({"error": "tamper_check_failed", "ok": False}, sys.stderr)
            return 1
        _emit({"detected": True, "ok": True, "operation": "tamper-check"})
    return 0


def main() -> int:
    try:
        return _run_demo()
    except (DemoGenerationError, OSError, subprocess.SubprocessError):
        _emit({"error": "demo_runtime_failed", "ok": False}, sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
