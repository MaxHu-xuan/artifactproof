# Release Process

Releases are maintainer-operated. Publishing a Git tag, GitHub release, or
package index upload is a separate action that requires an explicit review.

## Candidate checks

1. Confirm the working tree contains only intended, reviewable source files.
2. Run the unit tests and both privacy-audit modes:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
   PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
   ```

3. Build from a clean checkout, unpack the source distribution, and run
   `scripts/privacy_audit.py --sdist` inside that exact tree.
   Set the public project timestamp before building so wheel metadata cannot
   inherit local file times:

   - macOS or Linux: `export SOURCE_DATE_EPOCH=946684800`
   - Windows PowerShell: `$env:SOURCE_DATE_EPOCH = "946684800"`

   Then run `python -m build`.
4. Install the wheel into a fresh virtual environment with no project checkout
   on `PYTHONPATH`; verify `artifactproof --version` and a deterministic
   synthetic create/verify cycle.
5. Never upload the raw setuptools sdist: its tar headers may retain the build
   account and local file times. Create the upload candidate with the bundled
   canonicalizer, using the documented project epoch:

   ```bash
   python scripts/canonicalize_sdist.py --self-test
   python scripts/canonicalize_sdist.py --dist-dir dist --output-dir canonical-dist --source-date-epoch 946684800
   ```

   The canonicalizer fails closed on links, special files, duplicate or unsafe
   paths, and oversized input. It sets uid/gid to zero, removes user/group and
   optional gzip metadata, fixes member times and modes, and verifies that file
   contents are unchanged. Build the canonical candidate twice in separate
   clean directories and compare artifact hashes. Record SHA-256 checksums and
   the source commit.
6. Review [THREAT_MODEL.md](THREAT_MODEL.md), [SECURITY.md](SECURITY.md), the
   changelog, package metadata, and every distributed file.

Do not upload signing keys, private receipts, real artifacts, build caches, or
test output containing local paths. The first public release should be tagged
`v0.1.0` only after the private candidate and CI matrix are approved.
Source publication may proceed without release assets. Only the sdist from
`canonical-dist` may be reviewed for upload; never upload the raw archive from
`dist`.
