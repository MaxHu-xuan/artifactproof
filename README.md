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

## What problem does ArtifactProof solve? / 它解决什么问题？

When an AI agent, document generator, or CI pipeline creates a PowerPoint file,
a successful QA run does not by itself prove that the delivered file contains
the same bytes that were checked. ArtifactProof is an offline PPTX integrity
checker and tamper-evident QA receipt generator. It binds the exact presentation,
named evidence files, and a machine-readable check result into one HMAC-signed
receipt.

当 AI Agent、文档生成器或自动化流水线产出 PowerPoint 时，“检查通过”并不能单独证明
最终交付的文件就是当时被检查的那一份。ArtifactProof 提供离线 PPTX 结构校验和防篡改
质量凭证，把演示文稿的精确字节、外部验收证据以及机器可读的检查结果绑定在同一份
HMAC 签名收据中。

Typical uses include:

- checking a generated `.pptx` package before an automated delivery step;
- detecting replacement or mutation between QA, review, archival, and delivery;
- binding render manifests, accessibility reports, or other external QA evidence
  to the exact presentation that was checked;
- giving a later verifier a deterministic, network-free integrity check.

ArtifactProof is deliberately narrower than a PowerPoint design reviewer,
Office renderer, antivirus scanner, document fact-checker, or delivery tracker.
Those systems can produce evidence for ArtifactProof to bind, but ArtifactProof
does not claim to replace them.

## Project status

Version 0.1.0 is a review-ready pre-release. The receipt schema is explicit,
but the Python API and CLI may still change before 1.0. The package has not been
published to PyPI; install it from a reviewed checkout or release artifact.

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

CI covers Python 3.11 through 3.14 on Ubuntu, plus Python 3.11 and 3.14 on
macOS and Windows. Archive member names always use POSIX rules, regardless of
the host operating system.

| Host | Receipt-file protection | Notable behavior |
| --- | --- | --- |
| Linux and macOS | New receipts are written with mode `0600` | Atomic replacement uses `os.replace` on the destination filesystem. |
| Windows | Receipts inherit the destination directory's DACL | Keep receipts in an account-private directory; another process holding the destination open can block replacement. |

## Quick start on Linux, macOS, and Windows

From the repository root:

```bash
python3 -m pip install .
artifactproof --version
```

On Windows PowerShell:

```powershell
py -3.11 -m pip install .
artifactproof --version
```

Set a signing key in an environment variable. Use at least 32 random bytes. A
base64-encoded value is preferred. On Linux or macOS:

```bash
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

On Windows PowerShell:

```powershell
$env:ARTIFACTPROOF_SIGNING_KEY = 'base64:REPLACE_WITH_BASE64_KEY'
```

Do not reuse the placeholder. Supply the real value through the operating
system, CI secret store, or another caller-controlled secret manager.

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

The equivalent Windows PowerShell commands can be entered as single lines:

```powershell
artifactproof create deck.pptx --evidence slides=render-manifest.json --receipt deck.receipt.json --key-id local-ci
artifactproof verify deck.pptx --evidence slides=render-manifest.json --receipt deck.receipt.json --expected-key-id local-ci
```

Successful CLI operations emit small JSON objects so automation can make a
deterministic pass/fail decision. Expected failures use stable error codes and
do not echo the signing key, file contents, or full input paths.

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

## Frequently asked questions / 常见问题

### Is ArtifactProof a PowerPoint validator?

It is a conservative structural validator for Transitional OOXML `.pptx`
packages. It checks ZIP and core OPC relationships without opening Microsoft
Office or extracting the archive. It is not a complete ECMA-376 conformance
checker and it does not score slide design.

### Why use a receipt instead of only a SHA-256 checksum?

A checksum detects a byte change only when the verifier already has a trusted
reference checksum. ArtifactProof signs structured metadata that includes the
artifact digest, evidence digests, and QA result. A verifier with the shared
HMAC key can check that binding. HMAC does not provide public verification,
encryption, timestamp authority, or non-repudiation.

### Does ArtifactProof upload or send a presentation?

No. The shipped runtime uses only the Python standard library and has no network
client. Artifact and evidence contents stay on the caller's machine. Receipt
metadata includes the artifact basename, logical evidence names, and `key_id`,
so callers should still choose non-sensitive names.

### Does it work on Windows, macOS, and Linux?

Yes. CI exercises supported Python versions across all three operating systems.
The verification format is platform-independent. On Windows, receipt privacy
depends on the destination directory's DACL rather than POSIX `0600` mode, and
an open destination file may prevent atomic replacement.

### Can it validate PDF, DOCX, images, or arbitrary generated files?

Version 0.1.0 ships a PPTX adapter and the CLI uses that adapter. Python callers
can provide a custom `qa_runner`, but additional formats need their own threat
model and tests; this repository does not claim built-in validation for them.

### Can it prove that a presentation is visually good or factually correct?

No. Use a renderer, visual review, accessibility checker, or fact-checking
system for those questions. Their result files can be supplied as named evidence
so the receipt later proves which exact evidence accompanied which exact PPTX.

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

See [THREAT_MODEL.md](THREAT_MODEL.md), [SECURITY.md](SECURITY.md), and
[SUPPORT.md](SUPPORT.md) before embedding ArtifactProof into a delivery system.
