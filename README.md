# ArtifactProof（交付物验真）

ArtifactProof creates offline, hash-bound quality-assurance receipts for generated
files. The first adapter performs conservative structural checks on PowerPoint
`.pptx` packages without LibreOffice, Microsoft Office, network access, or
third-party Python dependencies.

中文简介：为生成的 PPTX 创建离线、可校验且与文件哈希绑定的质量验收凭证，防止“验收后被替换”。

能力边界：当前只检查 PPTX 包结构、文件哈希、证据绑定和收据签名；不证明内容真实、视觉质量、作者身份或渠道送达。

This repository is a clean-room prototype. Its code and tests were written from
scratch and use only synthetic fixtures.

ArtifactProof is licensed under the Apache License, Version 2.0. See
[`LICENSE`](LICENSE).

## What it proves

For each receipt, ArtifactProof records:

- the final artifact SHA-256 and byte size;
- SHA-256 and size for named evidence files;
- a machine-readable QA result;
- an HMAC-SHA256 signature over the canonical receipt payload.

The create flow hashes the artifact, runs QA, and hashes it again. If the file
changes during QA, receipt creation stops. Verification re-hashes the delivered
artifact and all declared evidence, so a post-QA replacement is rejected.

For format v1, the HMAC input retains `signature.algorithm` and
`signature.key_id` but removes `signature.value`. The remaining receipt is
serialized as UTF-8 JSON with keys sorted, no insignificant whitespace,
non-ASCII characters preserved, and non-finite numbers forbidden. This rule is
part of `artifactproof.receipt.v1` and must not be changed without a new schema
version.

## What it does not prove

The built-in PPTX check validates package integrity and basic relationships. It
does **not** render slides or judge typography, aesthetics, accessibility,
semantic correctness, or whether a recipient actually opened a message. A
rendering or channel-delivery adapter can produce evidence files whose hashes
are then bound into the receipt.

## Requirements

- Python 3.11 or newer
- Standard library only at runtime
- No network access

## Local use

Set a signing key in an environment variable. Use at least 32 random bytes. A
base64-encoded value is preferred:

```bash
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

Create a receipt:

```bash
artifactproof create deck.pptx \
  --evidence slides=render-manifest.json \
  --receipt deck.receipt.json \
  --key-id local-ci
```

Verify the exact artifact and evidence later:

```bash
artifactproof verify deck.pptx \
  --evidence slides=render-manifest.json \
  --receipt deck.receipt.json \
  --expected-key-id local-ci
```

The CLI deliberately has no raw `--key` option. It accepts a key only through
the selected environment variable (default:
`ARTIFACTPROOF_SIGNING_KEY`). The Python API accepts key bytes as an explicit
parameter. Keys are never written to receipts or normal CLI output.
`key_id`, the artifact basename, and logical evidence names are public receipt
metadata; do not put secrets or private identifiers in those fields.

`write_receipt` requires the artifact and evidence paths as
`protected_paths`. It rejects exact paths, normalized aliases, symlinks and
hard links rather than risking replacement of an input file.

Receipt writes use a temporary file in the destination directory followed by
`os.replace`, so the replacement stays on one filesystem. On POSIX the
temporary and resulting file mode is `0600`. Windows does not map POSIX mode
bits to user-only ACLs; there the file inherits the destination directory's
ACL, so place receipts in a directory already restricted to the intended
account. Windows may also refuse replacement while another process has the
destination open; this is reported as a stable input error and the temporary
file is removed.

## Python API

```python
from pathlib import Path
from artifactproof import create_receipt, verify_receipt, write_receipt

key = b"a 32-byte-or-longer secret supplied by the caller"
receipt = create_receipt(
    Path("deck.pptx"),
    evidence={"slides": Path("render-manifest.json")},
    signing_key=key,
    key_id="local-ci",
)
write_receipt(
    Path("deck.receipt.json"),
    receipt,
    protected_paths=[Path("deck.pptx"), Path("render-manifest.json")],
)
verify_receipt(
    receipt,
    Path("deck.pptx"),
    evidence={"slides": Path("render-manifest.json")},
    signing_key=key,
    expected_key_id="local-ci",
)
```

## PPTX checks

The dependency-free adapter checks:

- ZIP integrity, duplicate members, encryption flags, unsafe names and common
  decompression-bomb indicators;
- required OPC parts and parseable UTF-8 XML; DTD/entity declarations and
  UTF-16/UTF-32 encodings are rejected before parsing;
- exact Transitional OOXML package and slide relationship types;
- presentation-to-slide relationships;
- unique slide relationship IDs and targets;
- presence and basic XML shape of every referenced slide.

It never extracts the archive to disk.

The v1 ZIP safety limits are 5,000 members, 256 MiB total declared expanded
size, 8 MiB per inspected XML part, and a maximum 200:1 ratio for members larger
than 1 MiB. These conservative limits may reject unusually large but valid
presentations.

The v1 adapter intentionally fails closed on Strict OOXML namespaces. Support
for Strict OOXML should be added as a separately tested profile rather than by
accepting relationship URI suffixes.

ZIP and OPC member names are interpreted with POSIX separators on every host.
Backslashes, drive-qualified or UNC-style names, traversal/dot aliases, and
non-canonical content-type part names are rejected, including when the CLI is
running on Windows.

## Receipt schema

[`schema/receipt.schema.json`](schema/receipt.schema.json) is a JSON Schema
2020-12 description of format `artifactproof.receipt.v1`. The implementation
also performs strict shape checks without requiring a JSON Schema library.
JSON Schema cannot require uniqueness by one object property, so the schema's
`$comment` records the additional runtime rule that evidence names are unique.
Receipt timestamps use canonical UTC syntax
`YYYY-MM-DDTHH:MM:SS[.fraction]Z`; offsets, omitted `Z`, space separators, and
impossible calendar dates are rejected. Receipt files larger than 1 MiB are
rejected before JSON parsing. Loading reads at most 1 MiB plus one byte and
checks file identity before and after the read, so a file that grows or is
replaced between the initial metadata check and open fails closed.

## Development

Run the synthetic test suite without installing the package:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run the values-free publication audit against the exact release tree:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
```

Audit an extracted source distribution with the explicit sdist profile:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py \
  --sdist unpacked/artifactproof-0.1.0
```

When running the audit copy contained inside an extracted sdist, also pass the
profile to its self-test:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --sdist
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --sdist --self-test
```

The sdist profile permits and scans only the generated
`src/artifactproof.egg-info` directory. Any other `.egg-info`, cache, build, or
distribution directory remains a finding. Source-tree audits do not enable this
exception.

Run these commands against a clean release tree. The privacy audit deliberately
flags cache, build, and distribution artifacts that are not part of the reviewed
source tree.

Audit findings contain only relative paths, stable codes, and counts. Matching
content, credentials, personal data, and absolute input paths are never emitted.

CI runs all supported Python versions (3.11 through 3.14) on Ubuntu, plus the
oldest and newest supported versions on macOS and Windows. Symlink tests are
skipped only when the host does not permit creating symlinks; hard-link and
path-alias checks remain active.

See [THREAT_MODEL.md](THREAT_MODEL.md) and [SECURITY.md](SECURITY.md) before
embedding ArtifactProof into a delivery system.
