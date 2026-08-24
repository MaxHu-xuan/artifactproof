# Release Process

Releases are maintainer-operated. Publishing a Git tag, GitHub release, or
package index upload is a separate action that requires an explicit review.

## Candidate checks

1. Confirm the working tree contains only intended, reviewable source files.
2. Run the deterministic synthetic demo, unit tests, canonicalizer self-test,
   and both privacy-audit modes.

   Linux or macOS:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python3 examples/run_demo.py
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/canonicalize_sdist.py --self-test
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
   ```

   Windows PowerShell:

   ```powershell
   $env:PYTHONDONTWRITEBYTECODE = "1"
   $env:PYTHONUTF8 = "1"
   py -3 examples\run_demo.py
   $previousPythonPath = $env:PYTHONPATH
   $env:PYTHONPATH = "src"
   py -3 -m unittest discover -s tests -v
   $env:PYTHONPATH = $previousPythonPath
   py -3 scripts\canonicalize_sdist.py --self-test
   py -3 scripts\privacy_audit.py
   py -3 scripts\privacy_audit.py --self-test
   ```

3. Build from a clean checkout, unpack the source distribution, and run
   `scripts/privacy_audit.py --sdist` inside that exact tree.
   Set the public project timestamp before building so wheel metadata cannot
   inherit local file times:

   Linux or macOS:

   ```bash
   export SOURCE_DATE_EPOCH=946684800
   python3 -m venv .venv
   . .venv/bin/activate
   python -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
   python -m build --no-isolation
   ```

   Windows PowerShell:

   ```powershell
   $env:SOURCE_DATE_EPOCH = "946684800"
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install "build==1.3.0" "setuptools==77.0.3" "wheel==0.46.2"
   .\.venv\Scripts\python.exe -m build --no-isolation
   ```

   Record all three pinned tool versions. `--no-isolation` is required here so
   the build does not silently create a second environment with newer,
   unrecorded backend tooling.
4. Install the wheel into a fresh virtual environment with no project checkout
   on `PYTHONPATH`; verify `artifactproof --version` and a deterministic
   synthetic create/verify cycle.
5. Never upload the raw setuptools sdist: its tar headers may retain the build
   account and local file times. Create the upload candidate with the bundled
   canonicalizer, using the documented project epoch:

   Linux or macOS:

   ```bash
   python3 scripts/canonicalize_sdist.py --self-test
   python3 scripts/canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   Windows PowerShell:

   ```powershell
   py -3 scripts\canonicalize_sdist.py --self-test
   py -3 scripts\canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   The canonicalizer fails closed on links, special files, duplicate or unsafe
   paths, and oversized input. It sets uid/gid to zero, removes user/group and
   optional gzip metadata, fixes member times and modes, and verifies that file
   contents are unchanged. Build the canonical candidate twice in separate
   clean directories and compare artifact hashes. Record SHA-256 checksums and
   the source commit.
6. Review [THREAT_MODEL.md](THREAT_MODEL.md), [SECURITY.md](SECURITY.md),
   [RELEASE_NOTES.md](RELEASE_NOTES.md), the changelog, package metadata, and
   every distributed file. Confirm that the release notes describe the exact
   candidate and add checksums only after the final artifacts are selected.

Do not upload signing keys, private receipts, real artifacts, build caches, or
test output containing local paths. Do not include `demo-output`, generated
PPTX files, or generated synthetic evidence in the release. The first public
release should be tagged `v0.1.0` only after the private candidate and CI matrix
are approved.
Source publication may proceed without release assets. Only the sdist from
`canonical-dist` may be reviewed for upload; never upload the raw archive from
`dist`.
