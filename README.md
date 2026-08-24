# ArtifactProof（PPTX 交付物验真）

[![CI](https://github.com/MaxHu-xuan/artifactproof/actions/workflows/ci.yml/badge.svg)](https://github.com/MaxHu-xuan/artifactproof/actions/workflows/ci.yml)

[中文说明](#中文说明) · [English overview](#english-overview) · [Technical reference](#technical-reference)

## 中文说明

### ArtifactProof 解决什么问题？

一份 PPTX 通过检查后，可能还要经历审批、重命名、上传、下载和转发。到了真正交付时，
怎样确认它仍是当时检查过的那一份？

ArtifactProof 是一个本地、离线的 PowerPoint（.pptx）交付物验真工具。它不依赖文件名或
修改时间，而是根据文件内容计算 SHA-256 校验值，把结构检查结果和外部质检证据写入一份
HMAC-SHA256 签名收据。以后再次验证时，只要 PPTX、证据文件或收据发生不一致，验证就会
失败。

它适合补上 PPTX 质量检查与最终交付之间的完整性缺口，让检查结果对应到准确的文件，
而不是只靠文件名或聊天记录判断。

### 适用场景

- AI 工具或自动化流程生成 PPTX，需要在交付前检查基本结构，并保留可复验的结果。
- 演示文稿经过质检、审批、归档和发送，需要发现中途替换或误传。
- 渲染报告、可访问性报告、人工验收记录或其他证据需要对应到准确的 PPTX 文件。
- 团队希望在 CI、内网或无网络环境中增加一道稳定的文件完整性检查。

### 它怎样工作？

1. `create` 在检查前后分别计算 PPTX 的 SHA-256；如果检查过程中有其他进程修改文件，
   收据不会创建。
2. 内置检查器验证 PPTX 的 ZIP、OOXML 基本结构和关键关系。提供 `--evidence` 时，外部
   报告也会计算 SHA-256 并写入收据。
3. 收据记录文件摘要、字节大小、检查结果和证据摘要，再使用调用方提供的共享密钥生成
   HMAC-SHA256 签名。
4. `verify` 重新读取 PPTX 和证据，核对摘要、签名与 `key_id`。任何不一致都会得到失败
   结果，而不是继续把文件当作已验证版本。

最终得到的是一份小型 JSON 收据和适合自动化读取的成功或失败结果。收据不包含 PPTX
正文或证据正文。默认情况下，它会保存 PPTX 的源文件名；如果该名称包含客户名称或内部
标识，可以用 `--artifact-name` 改为由调用方选择的中性逻辑名称。工具会检查名称格式，
但调用方仍须确保名称不含敏感信息。证据逻辑名称和 `key_id` 也会写入收据，同样不应包含
敏感信息。

### 快速开始

#### 1. 安装并设置签名密钥

需要 Python 3.11 或更高版本。0.1.0 尚未发布到 PyPI，请从已经审核的代码目录安装。

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

请将占位值换成由至少 32 个随机字节生成的密钥，并保存在操作系统、CI 密钥库或团队使用
的密钥管理工具中。不要把真实密钥写进代码、收据或命令参数。

#### 2. 检查 PPTX 并创建收据

Linux 或 macOS：

```bash
artifactproof create deck.pptx \
  --artifact-name approved-deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --key-id local-ci
```

Windows PowerShell：

```powershell
artifactproof create deck.pptx --artifact-name approved-deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
```

没有外部报告时可以省略 `--evidence`。如果创建收据时绑定了证据，验证时必须提供逻辑名称
相同、内容也相同的文件。`--artifact-name` 只控制收据公开的逻辑名称，不改变读取哪个
文件，也不参与路径匹配；验证仍以 SHA-256 和字节大小为准，因此复验时文件可以换一个
本地名称。

#### 3. 在交付前或接收后复验

Linux 或 macOS：

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

创建与验证必须使用同一把签名密钥。成功时命令会返回简短的 JSON；PPTX、证据、签名或
预期的密钥标识不一致时会返回失败。

### ArtifactProof 能验证什么，不能验证什么？

- 能验证：当前 PPTX 和外部证据是否与签名收据记录的字节内容一致。
- 能检查：Transitional OOXML `.pptx` 的 ZIP 安全边界、必要部件、XML 和基础关系。
- 能辅助：把 PPTX 质检证据与最终文件绑定，并在交付前后复核文件完整性。
- 不能代替：代码签名、公开密钥签名、可信时间戳或通用的文件安全与发布系统。
- 不能判断：设计美感、排版、可访问性、事实准确性、内容质量、恶意内容或收件人是否
  已经收到并打开文件。

文件生成成功、基础结构检查通过、视觉验收通过、当前文件未被替换和文件真实送达，是
不同的结论。ArtifactProof 直接检查基础结构和当前字节是否匹配；外部视觉验收或交付报告
可以作为证据文件绑定，但 ArtifactProof 不会独立证明报告内容真实，也不会把报告存在
误写成已经交付。

HMAC 适合持有同一共享密钥的团队。它不能区分共享该密钥的不同成员，也不提供公开验证
或不可否认性。保守的 ZIP 安全限制可能拒绝体积异常大的合法 PPTX。0.1.0 是预发布版本，
命令行和 Python API 在 1.0 前仍可能调整。

### 常见问题

#### 如何确认交付的 PPTX 没有被替换？

在质检通过时运行 `artifactproof create`，保存 PPTX、收据和密钥；在发送前或接收后运行
`artifactproof verify`。验证通过表示当前文件、声明的证据和签名收据彼此一致。它不表示
文件永远不会再变化，因此应尽量在实际交付或使用前复验。

#### ArtifactProof 与单独保存 SHA-256 checksum 有什么区别？

单独的 checksum 需要另一个可信位置保存参考值。ArtifactProof 把 PPTX 摘要、证据摘要
和检查结果放进同一份结构化收据，并用 HMAC-SHA256 签名。验证方仍然需要通过安全渠道
获得正确的共享密钥；工具不会自动建立这层信任。

#### 如何避免收据暴露原始 PPTX 文件名？

创建时加入 `--artifact-name approved-deck.pptx`。收据只保存这个逻辑名称，不保存源路径或
源文件名。逻辑名称会进入签名内容，验证时不能修改；但验证不要求本地文件继续使用
同一个名称。逻辑名称是公开元数据，不是文件路径；为减少跨平台误用，命令会拒绝路径
分隔符、首尾空格、结尾句点，以及 Windows 文件名保留字符和设备名。名称格式通过不代表
内容不敏感，因此不要填写客户名称、账号、项目代号或其他敏感信息。

#### 文件会上传到网络吗？

不会。当前运行时代码只使用 Python 标准库，不包含网络客户端。PPTX、证据和收据都留在
调用方选择的本地存储位置。

#### Windows、macOS 和 Linux 都能使用吗？

可以，收据格式跨平台一致。Linux 和 macOS 上的新收据使用 `0600` 权限；Windows 上的
文件权限继承目标目录的 DACL，因此应把收据放在当前账户专用的目录中。

#### 能直接检查 PDF、DOCX 或图片吗？

0.1.0 的内置检查器仅支持 PPTX。Python 调用方可以提供自定义 `qa_runner`，但其他格式
需要各自的威胁模型和测试，不能视为项目已经内置支持。

#### 能判断 PPT 是否美观或内容是否正确吗？

不能。视觉审查、可访问性检查和事实核验需要其他工具或人工完成。可以把这些检查生成的
报告作为证据，让收据明确它们对应的是哪一份 PPTX。

## English Overview

### What problem does ArtifactProof solve?

A PPTX may pass review and then move through approval, renaming, upload,
download, and delivery. How can the recipient confirm that the final file is
still the exact presentation that passed the earlier check?

ArtifactProof is a local, offline artifact verification tool for PowerPoint
(.pptx) files. It uses the file contents rather than the filename or
modification time. The tool records a SHA-256 checksum, structural QA result,
and optional evidence in an HMAC-SHA256-signed receipt. Later verification
fails if the presentation, declared evidence, or receipt no longer matches.

It closes the integrity gap between PPTX quality review and final delivery by
keeping the review result tied to the exact file rather than relying on a
filename or chat record.

### When should you use it?

- An AI tool or automation pipeline creates a PPTX that needs a basic structural
  check and a result that can be verified later.
- A presentation passes through QA, approval, archival, and delivery, where an
  accidental or deliberate replacement needs to be detected.
- Render output, accessibility reports, human review records, or other evidence
  must stay associated with the exact PPTX that was checked.
- A team needs a deterministic file-integrity check in CI, on an internal
  network, or in an offline environment.

### How does it work?

1. `create` calculates the PPTX SHA-256 before and after QA. If another process
   changes the file while QA is running, no receipt is created.
2. The built-in checker validates the PPTX ZIP package, basic OOXML structure,
   and key relationships. Each `--evidence` file is hashed and added to the
   receipt.
3. The receipt records digests, byte sizes, QA results, and evidence, then signs
   that payload with an HMAC-SHA256 key supplied by the caller.
4. `verify` reads the PPTX and evidence again and checks their digests, the
   receipt signature, and `key_id`. Any mismatch produces a failure instead of
   treating the file as verified.

The output is a small JSON receipt plus stable success or failure results for
automation. It does not contain the presentation or evidence contents. By
default, it stores the PPTX basename. Use `--artifact-name` to replace a source
filename that contains a customer name or internal identifier with a neutral
logical name chosen by the caller. The tool validates the name's format, but
the caller remains responsible for keeping it non-sensitive. Logical evidence
names and `key_id` are also stored in the receipt and should not contain
sensitive information.

### Quick start

#### 1. Install and set a signing key

Python 3.11 or newer is required. Version 0.1.0 is not yet published to PyPI;
install it from a reviewed source checkout.

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
the real key in an operating-system or CI secret store, or another secret
manager controlled by your team. Never place it in source code, a receipt, or a
command argument.

#### 2. Check the PPTX and create a receipt

Linux or macOS:

```bash
artifactproof create deck.pptx \
  --artifact-name approved-deck.pptx \
  --evidence render=render-manifest.json \
  --receipt deck.receipt.json \
  --key-id local-ci
```

Windows PowerShell:

```powershell
artifactproof create deck.pptx --artifact-name approved-deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
```

Omit `--evidence` when there is no external report. If evidence is bound during
creation, verification requires a file with the same logical name and the same
contents. `--artifact-name` changes only the public label stored in the receipt;
it does not select a different input or add a path check. Verification still
uses SHA-256 and byte size, so the local file may have a different name later.

#### 3. Verify before delivery or after receipt

Linux or macOS:

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
returns a small JSON object. A mismatch in the PPTX, evidence, signature, or
expected key identifier returns a failure.

### What can ArtifactProof verify, and where does it stop?

- It verifies that the current PPTX and evidence bytes match an HMAC-signed
  receipt.
- It checks ZIP safety boundaries, required parts, XML, and basic relationships
  in Transitional OOXML `.pptx` files.
- It can bind PPTX review evidence to the final file and support integrity
  checks before and after delivery.
- It does not replace code signing, public-key signatures, trusted timestamps,
  or a general file-security and release system.
- It does not judge design, typography, accessibility, factual accuracy,
  content quality, malicious intent, or whether a recipient received or opened
  the file.

Generation success, structural validation, visual approval, exact-file
integrity, and actual delivery are separate claims. ArtifactProof directly
checks basic structure and byte identity. It can bind an external visual-review
or delivery report as evidence, but it does not independently prove that the
report is true or treat the presence of a report as proof of delivery.

HMAC works for teams that share the same secret. It cannot distinguish between
people who hold that key and does not provide public verification or
non-repudiation. Conservative ZIP limits may reject an unusually large valid
PPTX. Version 0.1.0 is a pre-release, so the CLI and Python API may change before
1.0.

### Frequently asked questions

#### How do I verify that a delivered PPTX was not replaced after QA?

Run `artifactproof create` when QA passes, retain the PPTX, receipt, and key, and
run `artifactproof verify` immediately before delivery or after receipt. A pass
means the current file, declared evidence, and signed receipt agree. It does not
prevent a later change, so verify as close as possible to the actual handoff or
use.

#### How is ArtifactProof different from saving a SHA-256 checksum?

A standalone checksum still needs a trusted place to store its reference value.
ArtifactProof puts the PPTX digest, evidence digests, and QA result in one
structured receipt and signs it with HMAC-SHA256. The verifier must still obtain
the correct shared key through a trusted channel; the tool does not create that
trust automatically.

#### How can I keep the original PPTX filename out of the receipt?

Add `--artifact-name approved-deck.pptx` when creating the receipt. The receipt
stores that logical name instead of the source path or basename. The logical
name is signed and cannot be edited later, but verification does not require the
local file to keep the same name. A logical name is public metadata, not a file
path. To reduce cross-platform ambiguity, the CLI rejects path separators,
surrounding whitespace, a trailing dot, and Windows-reserved filename
characters and device names. Passing these format checks does not make the
value private, so do not put customer names, account numbers, project codes, or
other sensitive identifiers in the logical name.

#### Does ArtifactProof upload a presentation?

No. The current runtime uses only the Python standard library and contains no
network client. The PPTX, evidence, and receipt remain in storage selected by
the caller.

#### Does it work on Windows, macOS, and Linux?

Yes. The receipt format is platform-independent. New receipts use mode `0600`
on Linux and macOS. On Windows, privacy depends on the destination directory
DACL, so use a directory restricted to the intended account.

#### Can it validate PDF, DOCX, or images?

The built-in checker in 0.1.0 supports PPTX only. Python callers can supply a
custom `qa_runner`, but each additional format needs its own threat model and
tests and is not claimed as built-in support.

#### Can it judge visual quality or factual accuracy?

No. Visual review, accessibility checks, and fact-checking require another tool
or a person. Their reports can be supplied as evidence so the receipt records
which exact PPTX they belong to.

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

The evidence input accepts a caller-selected report as opaque bytes.
ArtifactProof hashes that file and binds it to the PPTX receipt, but it does not
interpret the report or validate its conclusions.

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
`key_id`, the artifact name, and logical evidence names are public receipt
metadata. The create command stores the source basename by default; use
`--artifact-name` to substitute a caller-chosen logical name. The option
accepts 1 to 255 printable characters but rejects path separators, surrounding
whitespace, trailing dots, and characters reserved in common Windows
filenames, including reserved device names. Format validation does not detect
sensitive meaning; the caller must keep every public receipt field free of
secrets and private identifiers.

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
    artifact_name="approved-deck.pptx",
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
