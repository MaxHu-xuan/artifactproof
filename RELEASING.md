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
4. Install the wheel into a fresh virtual environment with no project checkout
   on `PYTHONPATH`; verify `artifactproof --version` and a deterministic
   synthetic create/verify cycle.
5. Pass the raw build through a reviewed canonical-archive builder using one
   fixed source timestamp. Build the canonical candidate twice in separate
   clean directories and compare artifact hashes. Record SHA-256 checksums and
   the source commit. A raw setuptools sdist may preserve checkout or temporary
   file mtimes, so matching member contents alone is not evidence of a
   byte-reproducible release archive.
6. Review [THREAT_MODEL.md](THREAT_MODEL.md), [SECURITY.md](SECURITY.md), the
   changelog, package metadata, and every distributed file.

Do not upload signing keys, private receipts, real artifacts, build caches, or
test output containing local paths. The first public release should be tagged
`v0.1.0` only after the private candidate and CI matrix are approved.
Source publication may proceed without release assets; do not attach a wheel or
sdist or publish to a package index until the canonical artifact gate passes.
