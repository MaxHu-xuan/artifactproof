# ArtifactProof（交付物验真）

[中文说明](#中文说明) · [English Overview](#english-overview) · [Technical reference](#technical-reference)

## 中文说明

ArtifactProof 帮助个人和团队确认：最终交付的 PowerPoint 文件，是否就是之前检查通过的
那一份。它在本地离线运行，为 PPTX 文件生成与文件内容绑定的验真收据；稍后再次验证时，
只要演示文稿或配套证据发生变化，验证就会失败。

如果你正在寻找离线 PPTX 结构校验、PowerPoint 文件验真、防篡改质量凭证或生成式文件
证据绑定工具，ArtifactProof 面向的就是这一类明确需求。

### 适合这些场景

- AI 工具或自动化流程生成 PPTX，需要在交付前做一次基础结构检查。
- 文件经过检查、审批、归档和发送等多个环节，需要确认中途没有被替换。
- 团队已有渲染报告、可访问性报告或其他验收证据，希望把证据与准确的 PPTX 绑定。
- 接收方需要在无网络环境中复核文件与验真收据是否一致。

### 三步使用

#### 第一步：安装并设置签名密钥

需要 Python 3.11 或更高版本。当前版本尚未发布到 PyPI，请从已经审核的代码目录安装。

Linux 或 macOS：

```bash
python3 -m pip install .
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

Windows PowerShell：

```powershell
py -3.11 -m pip install .
$env:ARTIFACTPROOF_SIGNING_KEY = 'base64:REPLACE_WITH_BASE64_KEY'
```

请把占位值替换为至少 32 个随机字节生成的密钥，并通过操作系统、CI 密钥库或团队自己的
密钥管理工具保存。不要把真实密钥写进代码、收据或命令参数。

#### 第二步：检查 PPTX 并生成收据

```bash
artifactproof create deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --key-id local-ci
```

Windows PowerShell 可以使用同一条单行命令：

```powershell
artifactproof create deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
```

如果没有外部证据文件，可以省略 `--evidence`。如果提供了证据，验证时必须提供同名且
内容一致的文件。

#### 第三步：交付前或接收后再次验证

```bash
artifactproof verify deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --expected-key-id local-ci
```

Windows PowerShell：

```powershell
artifactproof verify deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --expected-key-id local-ci
```

创建和验证必须使用同一把签名密钥。命令成功时会返回简短的 JSON 结果；文件、证据、
签名或预期的密钥标识不一致时，验证会失败。

### 你会得到什么

- 一份 JSON 收据，记录 PPTX 的 SHA-256、字节大小和基础结构检查结果。
- 外部证据文件的名称、SHA-256 和字节大小，前提是创建时提供了证据。
- 一份 HMAC-SHA256 签名，用于让持有同一密钥的验证方检查收据是否被修改。
- 稳定且便于自动化读取的成功或失败结果。

收据不会保存演示文稿或证据的正文，但会保存 PPTX 文件名、证据逻辑名称和 `key_id`。
这些名称也应避免包含个人信息或内部标识。

### 使用限制

- 当前内置检查只面向 Transitional OOXML 格式的 `.pptx` 文件。
- 它不渲染幻灯片，也不判断设计美感、排版、可访问性、事实准确性或内容质量。
- 它不是杀毒软件，不能证明文件没有恶意内容。
- 它不能证明消息已经发送、收到或打开。
- HMAC 适合共享密钥的团队验证，不提供公开签名、权威时间戳或不可否认性。
- 保守的 ZIP 安全限制可能拒绝体积异常大的合法演示文稿。
- 0.1.0 是预发布版本，命令行和 Python API 在 1.0 前仍可能调整。

### 常见问题

#### 文件会上传到网络吗？

不会。当前运行时代码只使用 Python 标准库，也不包含网络客户端。文件与证据留在调用者
选择的本地存储位置。

#### 与单独保存 SHA-256 有什么不同？

普通校验值只能在已有可信参考值时比较文件。ArtifactProof 把 PPTX 校验值、证据校验值
和检查结果放进同一份带 HMAC 签名的结构化收据，便于团队在后续环节一起复核。

#### Windows、macOS 和 Linux 都能使用吗？

可以。验证格式跨平台一致。Windows 上的收据权限继承目标目录的 DACL，不等同于
Linux 和 macOS 的 `0600` 权限，因此应把收据放在当前账户专用的目录中。

#### 能直接检查 PDF、DOCX 或图片吗？

不能。0.1.0 只内置 PPTX 检查器。Python 调用方可以提供自定义 `qa_runner`，但其他格式
需要单独的威胁模型和测试，不能视为当前项目已经支持。

#### 能判断 PPT 是否美观或内容是否正确吗？

不能。视觉审查、可访问性检查和事实核验需要其他工具或人工完成。你可以把这些检查生成的
报告作为证据交给 ArtifactProof，让收据记录它们对应的是哪一份准确的 PPTX。

## English Overview

ArtifactProof helps people and teams confirm that the PowerPoint file delivered
later is the same file that passed an earlier check. It runs locally and offline,
creates a receipt bound to the exact PPTX bytes, and rejects verification if the
presentation or any declared evidence changes.

It is designed for people looking for an offline PPTX integrity checker,
PowerPoint file verification, a tamper-evident QA receipt, or evidence binding
for generated artifacts.

### When to use it

- An AI tool or automation pipeline generates a PPTX that needs a structural
  check before delivery.
- A presentation moves through QA, approval, archival, and delivery, and the
  team needs to detect replacement along the way.
- Render reports, accessibility reports, or other QA evidence need to stay bound
  to the exact presentation that was checked.
- A recipient needs a deterministic verification step that works without a
  network connection.

### Three-step use

#### Step 1: Install and set the signing key

Python 3.11 or newer is required. This version is not on PyPI; install it from a
reviewed source checkout.

Linux or macOS:

```bash
python3 -m pip install .
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

Windows PowerShell:

```powershell
py -3.11 -m pip install .
$env:ARTIFACTPROOF_SIGNING_KEY = 'base64:REPLACE_WITH_BASE64_KEY'
```

Replace the placeholder with a key derived from at least 32 random bytes. Keep
the real key in the operating system, a CI secret store, or another
caller-controlled secret manager. Do not put it in source code, a receipt, or a
command argument.

#### Step 2: Check the PPTX and create a receipt

```bash
artifactproof create deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --key-id local-ci
```

Windows PowerShell can use the equivalent single-line command:

```powershell
artifactproof create deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
```

Omit `--evidence` when there is no external evidence file. When evidence is
declared, verification requires a file with the same logical name and content.

#### Step 3: Verify before delivery or after receipt

```bash
artifactproof verify deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --expected-key-id local-ci
```

Windows PowerShell:

```powershell
artifactproof verify deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --expected-key-id local-ci
```

Creation and verification must use the same signing key. A successful command
returns a small JSON result. Verification fails when the artifact, evidence,
signature, or expected key identifier does not match.

### What you get

- A JSON receipt containing the PPTX SHA-256, byte size, and structural check
  result.
- The name, SHA-256, and byte size of each declared evidence file.
- An HMAC-SHA256 signature that lets a verifier with the same key detect receipt
  modification.
- Stable success and failure results suitable for automation.

The receipt does not store presentation or evidence contents. It does store the
PPTX basename, logical evidence names, and `key_id`, so those names should not
contain personal or internal identifiers.

### Limits

- The built-in checker currently supports only Transitional OOXML `.pptx` files.
- It does not render slides or judge design, typography, accessibility, factual
  accuracy, or content quality.
- It is not antivirus software and does not prove that a file is harmless.
- It does not prove that a message was sent, received, or opened.
- HMAC supports shared-key team verification; it does not provide public
  signatures, trusted timestamps, or non-repudiation.
- Conservative ZIP safety limits may reject unusually large valid presentations.
- Version 0.1.0 is a pre-release; the CLI and Python API may change before 1.0.

### Frequently asked questions

#### Does ArtifactProof upload a presentation?

No. The shipped runtime uses only the Python standard library and has no network
client. Files and evidence remain in storage selected by the caller.

#### How is this different from storing only a SHA-256 checksum?

A checksum supports comparison only when the verifier already has a trusted
reference value. ArtifactProof places the PPTX digest, evidence digests, and QA
result in one HMAC-signed structured receipt so a team can verify them together.

#### Does it work on Windows, macOS, and Linux?

Yes. The receipt format is platform-independent. On Windows, receipt privacy
depends on the destination directory DACL rather than POSIX `0600`, so use a
directory restricted to the intended account.

#### Can it validate PDF, DOCX, or images?

Not with the built-in checker. Version 0.1.0 ships only a PPTX adapter. Python
callers can supply a custom `qa_runner`, but other formats need their own threat
model and tests and are not claimed as built-in support.

#### Can it judge visual quality or factual accuracy?

No. Visual review, accessibility checks, and fact-checking require another tool
or a person. Their reports can be supplied as evidence so the ArtifactProof
receipt records which exact PPTX those reports belong to.

## 技术参考说明

以下内容统一使用英文，供集成者、安全审查人员和维护者查阅。命令、API 名称、错误码和
收据字段保持原样，避免翻译造成歧义。

## Technical reference

### Project status

Version 0.1.0 is a review-ready pre-release. The receipt schema is explicit,
but the Python API and CLI may still change before 1.0. The package has not been
published to PyPI; install it from a reviewed checkout or release artifact.

This is a clean-room implementation written from scratch with synthetic test
fixtures. It is licensed under the Apache License, Version 2.0. See
[`LICENSE`](LICENSE).

### How receipt verification works

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

### Technical scope

The built-in PPTX check validates package integrity and basic relationships. It
does not render slides or judge typography, aesthetics, accessibility,
semantic correctness, or whether a recipient actually opened a message. A
rendering or channel-delivery adapter can produce evidence files whose hashes
are then bound into the receipt.

### Runtime and platform behavior

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

### CLI and receipt-file safety

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

### Python API

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

### PPTX checks

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

### Receipt schema

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

### Development

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
