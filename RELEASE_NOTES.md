# ArtifactProof 0.1.0 release notes

Status: unpublished release draft. No tag, package-index upload, or GitHub
release is implied by this file.

## What this release is for

ArtifactProof helps a team confirm that a delivered PowerPoint file is the same
PPTX that passed basic structural checks and was associated with selected
external QA evidence. It creates an offline HMAC-SHA256 receipt over the exact
PPTX and evidence bytes, then verifies that relationship later.

This is deliberately narrower than a general signing system or a complete
OOXML validator. It does not judge slide design, accessibility, factual
accuracy, malicious content, or successful delivery. External review or
delivery reports can be bound as opaque evidence, but ArtifactProof does not
validate their conclusions.

## Included in 0.1.0

- Offline `create` and `verify` commands with stable JSON results.
- SHA-256 identity for the PPTX and each named evidence file.
- HMAC-SHA256 receipts using a caller-supplied shared key.
- Conservative PPTX ZIP, XML, required-part, and relationship checks.
- Detection of artifact or evidence changes during receipt creation.
- Atomic receipt writes and values-free expected error output.
- A caller-chosen logical artifact name for keeping a sensitive source basename
  out of the receipt.
- Linux CI coverage for Python 3.11 through 3.14, plus Python 3.11 and 3.14
  coverage on macOS and Windows.
- A deterministic, fully synthetic PPTX demo with create, verify, and tamper
  detection.
- Source-tree, source-archive, and release privacy checks, plus deterministic
  source-archive canonicalization.

## Try the release candidate locally

From a reviewed source checkout with Python 3.11 or newer:

Linux or macOS:

```bash
python3 examples/run_demo.py
```

Windows PowerShell:

```powershell
py -3 examples\run_demo.py
```

The script creates only temporary synthetic files and removes them when it
finishes. Its built-in key is public demo material and must never be reused for
real receipts.

## Platform and compatibility notes

- The receipt data format is the same on Linux, macOS, and Windows.
- New receipts use mode `0600` on Linux and macOS. On Windows they inherit the
  destination directory's DACL.
- Version 0.1.0 supports Transitional OOXML `.pptx` files and may conservatively
  reject unusually large but otherwise valid packages.
- HMAC verification requires both sides to obtain the same secret through a
  trusted channel. It does not provide public verification, signer identity, or
  non-repudiation.
- The CLI and Python API may still change before 1.0.

## Publication checklist for maintainers

Before publishing, complete every step in [`RELEASING.md`](RELEASING.md),
review the exact distribution contents, and record SHA-256 checksums for the
approved wheel and canonical source archive. Checksums are intentionally not
listed in this draft because they must be calculated from the exact artifacts
selected for release.
