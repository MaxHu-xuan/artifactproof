# Changelog

All notable changes will be recorded here. This project uses semantic
versioning once a public release is published.

## 0.1.0 (release candidate)

- Create and verify HMAC-SHA256 receipts bound to artifact and evidence hashes.
- Add conservative, dependency-free PPTX package checks.
- Reject input mutation, unsafe receipt aliases, malformed receipts, and
  non-canonical archive paths.
- Provide stable, values-free CLI errors and a pre-publication privacy audit.
- Allow callers to replace a sensitive PPTX basename with a signed logical
  artifact name while keeping verification content-based.
- Add a cross-platform release gate that removes build-account metadata from
  source archives and fixes wheel timestamps to a public project epoch.
- Keep source-swap protection on Windows while avoiding incompatible
  path-stat and open-handle timestamp comparisons.
- Test Python 3.11 through 3.14 across Linux, macOS, and Windows.
