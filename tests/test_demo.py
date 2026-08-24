# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from artifactproof import inspect_pptx


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = PROJECT_ROOT / "examples" / "generate_demo.py"
RUNNER_PATH = PROJECT_ROOT / "examples" / "run_demo.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "artifactproof_synthetic_demo_generator",
        GENERATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("the synthetic demo generator could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "artifactproof_synthetic_demo_runner",
        RUNNER_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("the synthetic demo runner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(RUNNER_PATH.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


class SyntheticDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generator = _load_generator()
        cls.runner = _load_runner()

    def test_generated_inputs_are_deterministic_and_structurally_valid(self) -> None:
        with tempfile.TemporaryDirectory() as first_directory:
            with tempfile.TemporaryDirectory() as second_directory:
                first_pptx, first_evidence = self.generator.generate_demo(
                    Path(first_directory)
                )
                second_pptx, second_evidence = self.generator.generate_demo(
                    Path(second_directory)
                )

                self.assertEqual(first_pptx.read_bytes(), second_pptx.read_bytes())
                self.assertEqual(
                    first_evidence.read_bytes(),
                    second_evidence.read_bytes(),
                )
                result = inspect_pptx(first_pptx)
                self.assertTrue(result.passed)
                self.assertEqual(result.slide_count, 1)

                evidence = json.loads(first_evidence.read_text(encoding="utf-8"))
                self.assertEqual(
                    evidence["kind"],
                    "artifactproof.synthetic-demo.v1",
                )
                self.assertIn("not a visual-review", evidence["note"])

                with zipfile.ZipFile(first_pptx) as archive:
                    members = archive.infolist()
                self.assertEqual(
                    [member.filename for member in members],
                    sorted(member.filename for member in members),
                )
                self.assertTrue(
                    all(member.date_time == self.generator.ZIP_TIMESTAMP for member in members)
                )

    def test_generator_refuses_to_overwrite_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact, evidence = self.generator.generate_demo(root)
            artifact_before = artifact.read_bytes()
            evidence_before = evidence.read_bytes()

            with self.assertRaises(self.generator.DemoGenerationError):
                self.generator.generate_demo(root)

            self.assertEqual(artifact.read_bytes(), artifact_before)
            self.assertEqual(evidence.read_bytes(), evidence_before)

    def test_generator_failure_preserves_concurrent_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / self.generator.PPTX_NAME
            evidence = root / self.generator.EVIDENCE_NAME
            replacement = b"synthetic-user-owned-replacement"
            original_open = Path.open

            def raced_open(path, *args, **kwargs):
                if path == evidence and args and args[0] == "xb":
                    artifact.unlink()
                    with original_open(artifact, "xb") as stream:
                        stream.write(replacement)
                    raise OSError("synthetic second-create failure")
                return original_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", raced_open):
                with self.assertRaises(self.generator.DemoGenerationError):
                    self.generator.generate_demo(root)

            self.assertEqual(artifact.read_bytes(), replacement)
            self.assertFalse(evidence.exists())

    def test_end_to_end_demo_uses_real_cli_and_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "artifactproof"
            shutil.copytree(
                PROJECT_ROOT,
                checkout,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            environment = dict(os.environ)
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            environment["PYTHONUTF8"] = "1"
            process = subprocess.run(
                [sys.executable, str(checkout / "examples" / "run_demo.py")],
                cwd=str(checkout),
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stderr, "")
            self.assertEqual(
                process.stdout.splitlines(),
                [
                    '{"evidence":"synthetic-review.json","ok":true,"operation":"generate","pptx":"synthetic-deck.pptx"}',
                    '{"ok":true,"operation":"create","qa":"pass","receipt_written":true}',
                    '{"ok":true,"operation":"verify","verified":true}',
                    '{"detected":true,"ok":true,"operation":"tamper-check"}',
                ],
            )
            self.assertEqual(list(checkout.rglob("__pycache__")), [])

    def test_runner_does_not_forward_unrelated_environment_values(self) -> None:
        marker_name = "ARTIFACTPROOF_SYNTHETIC_PRIVATE_ENV_MARKER"
        with mock.patch.dict(
            os.environ,
            {
                marker_name: "synthetic-private-value",
                "PYTHONPATH": "synthetic-untrusted-path",
            },
        ):
            environment = self.runner._environment()

        self.assertNotIn(marker_name, environment)
        self.assertEqual(environment["PYTHONPATH"], str(PROJECT_ROOT / "src"))
        self.assertEqual(
            environment["ARTIFACTPROOF_SIGNING_KEY"],
            self.runner.DEMO_KEY,
        )

    def test_runner_timeout_is_bounded_and_redacted(self) -> None:
        private_marker = "synthetic-private-command-path"
        timeout = subprocess.TimeoutExpired(
            [private_marker],
            self.runner.COMMAND_TIMEOUT_SECONDS,
        )
        with mock.patch.object(
            self.runner.subprocess,
            "run",
            side_effect=timeout,
        ) as run:
            with mock.patch.object(self.runner, "_emit") as emit:
                result = self.runner.main()

        self.assertEqual(result, 1)
        self.assertEqual(
            run.call_args.kwargs["timeout"],
            self.runner.COMMAND_TIMEOUT_SECONDS,
        )
        emit.assert_called_with(
            {"error": "demo_runtime_failed", "ok": False},
            sys.stderr,
        )
        self.assertNotIn(private_marker, repr(emit.call_args_list))


if __name__ == "__main__":
    unittest.main()
