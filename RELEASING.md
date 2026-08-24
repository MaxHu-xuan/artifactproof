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
   candidate. Keep final checksums in the external `SHA256SUMS` release asset,
   not in a file included by the source distribution; otherwise recording a
   checksum would change the archive it describes.

Do not upload signing keys, private receipts, real artifacts, build caches, or
test output containing local paths. Do not include `demo-output`, generated
PPTX files, or generated synthetic evidence in the release. The first public
release should be tagged `v0.1.0` only after the private candidate and CI matrix
are approved.
Only the sdist from `canonical-dist` may be reviewed for upload; never upload
the raw archive from `dist`.

## Trusted PyPI publication

The publishing workflow is `.github/workflows/publish-pypi.yml`. It runs only
when a GitHub Release is published. The workflow file and all release content
must therefore already be merged into the protected `main` branch before the
release is prepared.

1. Create the final `v0.1.0` tag at the reviewed commit on `main`, then create a
   **draft** GitHub Release for that tag. Do not mark the release as a
   prerelease.
2. Upload exactly these five assets to the draft Release, with no additional
   uploaded assets:

   - `SOURCE_COMMIT`
   - `SHA256SUMS`
   - `artifactproof-0.1.0.cdx.json`
   - `artifactproof-0.1.0-py3-none-any.whl`
   - `artifactproof-0.1.0.tar.gz`

   `SOURCE_COMMIT` contains only the full tag commit ID. `SHA256SUMS` contains
   exactly three entries: the wheel, the canonical sdist, and the SBOM. Each
   entry uses a lowercase SHA-256 digest, two spaces, and the exact filename.
   Re-run the candidate checks after any source or release-document change;
   `RELEASING.md` is included in the sdist, so editing it changes that archive.
3. In GitHub, create an environment named `pypi`. Require a maintainer review,
   allow deployments only from protected release tags, and store no secrets in
   the environment. If there is only one maintainer, do not enable prevention
   of self-review until a second trusted reviewer is available.
4. For the first PyPI release, register a pending Trusted Publisher with these
   exact values:

   - PyPI project: `artifactproof`
   - GitHub owner: `MaxHu-xuan`
   - GitHub repository: `artifactproof`
   - Workflow filename: `publish-pypi.yml`
   - Environment: `pypi`

5. Review the draft Release and its five assets, then publish the GitHub
   Release. The first workflow job checks the event, tag, `main` ancestry,
   source commit, checksums, SBOM identity, canonical sdist, privacy gates, and
   offline wheel installation without OIDC permission. It stores only the
   verified wheel and canonical sdist as an immutable Actions artifact.
6. Inspect that verification job before approving the protected `pypi`
   environment. The publishing job performs no checkout or build. It downloads
   only the verified Actions artifact and exchanges GitHub OIDC identity for a
   short-lived PyPI publishing credential.

Do not create or store a PyPI API token in GitHub, the repository, an
environment, a local file, or a release asset. Trusted Publishing requires only
the publishing job's job-scoped `id-token: write` permission; the verification
job has `contents: read` and no OIDC permission.

## Failed or partial publication

PyPI upload is not an all-or-nothing transaction. A failed workflow can mean
that neither distribution was uploaded, or that one approved file reached PyPI
before the other upload failed. The publishing action deliberately uses
`skip-existing: false`, so a retry cannot silently treat an existing filename
as success.

After any publishing failure, keep the workflow failed and compare the exact
PyPI file list and hashes with the approved `SHA256SUMS` asset before taking
further action. If nothing was uploaded, the failed publishing job may be
retried. If only an approved file was uploaded, stop and use a separately
reviewed recovery that submits only the missing approved file. If any published
hash is wrong, do not try to overwrite or reuse that filename; treat it as a
release incident and publish a corrected new version after remediation.
