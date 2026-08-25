# ArtifactProof（PPTX 交付物验真）

[![CI](https://github.com/MaxHu-xuan/artifactproof/actions/workflows/ci.yml/badge.svg)](https://github.com/MaxHu-xuan/artifactproof/actions/workflows/ci.yml)

中文导航：[中文说明](#中文说明) · [中文项目资料](#中文项目资料)

English navigation: [English overview](#english-overview) · [Technical reference](#technical-reference)

[ArtifactProof](https://github.com/MaxHu-xuan/artifactproof) · [TaskStateGuard](https://github.com/MaxHu-xuan/task-state-guard) · [ChatArchiveGuard](https://github.com/MaxHu-xuan/chat-archive-guard)

## 中文说明

### 检查通过的 PPTX，交付时还是同一份吗？

一份 PPTX 通过检查后，可能还要经历审批、重命名、上传、下载和转发。到了真正交付时，
文件名可能没变，文件内容却已经被替换；也可能拿着正确的质检报告，发出的却是另一版。

ArtifactProof 在本地为最终 PPTX 计算 SHA-256，执行基础结构检查，并把调用方选择的外部
质检证据一起绑定到 HMAC-SHA256 收据。交付前或接收后再次验证，可以确认当前 PPTX 与
提供的证据字节是否仍和该收据记录一致。

它不上传文件，也不依赖文件名和修改时间。它不是通用数字签名系统，不做完整 OOXML 语义
验证，也不判断设计美感；它专注于补上 PPTX 基础结构检查、外部 QA 证据与最终交付文件
之间的完整性缺口。

### 60 秒试跑

需要 Python 3.11 或更高版本。演示不需要安装、不访问网络，也不读取你的 PPTX 或密钥；
它只在临时目录生成一页合成演示稿，运行真实的 `create` 和 `verify` 命令，再确认文件被
改动后验证会失败。

Linux 或 macOS：

```bash
python3 examples/run_demo.py
```

Windows PowerShell：

```powershell
py -3 examples\run_demo.py
```

预期输出：

```json
{"evidence":"synthetic-review.json","ok":true,"operation":"generate","pptx":"synthetic-deck.pptx"}
{"ok":true,"operation":"create","qa":"pass","receipt_written":true}
{"ok":true,"operation":"verify","verified":true}
{"detected":true,"ok":true,"operation":"tamper-check"}
```

最后一行表示篡改已被发现，不表示演示稿通过了视觉审查或已经真实送达。演示输入的生成
方式和数据边界见
[`examples/README.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/examples/README.md)。生成器不会覆盖已有路径；
若生成中途失败，它可能保留已经创建的纯合成文件，避免误删被并发进程替换的同名内容。

### 三个项目怎么选？

| 你要解决的问题 | 项目 |
| --- | --- |
| 确认最终 PPTX 及随附验收证据仍匹配结构检查后生成的 HMAC 签名收据 | [ArtifactProof（PPTX 交付物验真）](https://github.com/MaxHu-xuan/artifactproof) |
| 重启后核对卡住任务、超时与待投递状态，不把未知结果猜成成功 | [TaskStateGuard（任务状态守护）](https://github.com/MaxHu-xuan/task-state-guard) |
| 分享或迁移聊天导出前，本地检查疑似秘密、个人信息形态、格式、SQLite 与扫描盲区 | [ChatArchiveGuard（聊天归档守护）](https://github.com/MaxHu-xuan/chat-archive-guard) |

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

### 用于你自己的 PPTX

#### 1. 安装并设置签名密钥

需要 Python 3.11 或更高版本。对于已经发布到 PyPI 的版本，建议在独立虚拟环境中安装。

Linux 或 macOS：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install artifactproof
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install artifactproof
$env:ARTIFACTPROOF_SIGNING_KEY = 'base64:REPLACE_WITH_BASE64_KEY'
```

如果要测试开发版，请从已经审核的源码 checkout 根目录安装：Linux 或 macOS 使用
`python -m pip install .`，Windows 使用
`.\.venv\Scripts\python.exe -m pip install .`。

离线使用时，请从同一个 GitHub Release 下载 wheel 与 `SHA256SUMS`，并先核验 wheel。
在包含这两个文件的目录中，运行与你的平台对应的命令。

Linux：

```bash
grep '  artifactproof-0.1.0-py3-none-any.whl$' SHA256SUMS | sha256sum --check -
```

macOS：

```bash
grep '  artifactproof-0.1.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check
```

Windows PowerShell：

```powershell
$wheel = '.\artifactproof-0.1.0-py3-none-any.whl'
$entry = @(Get-Content .\SHA256SUMS | Where-Object {
    $_ -match '^[0-9a-f]{64}  artifactproof-0\.1\.0-py3-none-any\.whl$'
})
if ($entry.Count -ne 1) { throw 'wheel checksum entry missing or duplicated' }
$expected = ($entry[0] -split '  ', 2)[0]
$actual = (Get-FileHash $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'wheel SHA-256 mismatch' }
```

核验通过后，再使用 `--no-index --no-deps` 安装该 wheel；不要安装未经核验或来源不明的
同名文件。

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
.\.venv\Scripts\python.exe -m artifactproof create deck.pptx --artifact-name approved-deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
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
.\.venv\Scripts\python.exe -m artifactproof verify deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --expected-key-id local-ci
```

创建与验证必须使用同一把签名密钥。成功时命令会返回简短的 JSON；PPTX、证据、签名或
预期的密钥标识不一致时会返回失败。

### Linux、macOS 与 Windows 命令差异

收据格式和验证结论跨平台一致，主要差异在 Python 启动命令、虚拟环境激活、环境变量和
多行命令写法。

| 操作 | Linux | macOS | Windows PowerShell |
| --- | --- | --- | --- |
| 启动 Python | `python3` | `python3` | `py -3` |
| 创建虚拟环境 | `python3 -m venv .venv` | `python3 -m venv .venv` | `py -3 -m venv .venv` |
| 激活虚拟环境 | `source .venv/bin/activate` | `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| 设置签名密钥 | `export ARTIFACTPROOF_SIGNING_KEY='…'` | `export ARTIFACTPROOF_SIGNING_KEY='…'` | `$env:ARTIFACTPROOF_SIGNING_KEY = '…'` |
| 拆分长命令 | 行末使用 `\` | 行末使用 `\` | 行末使用反引号，或使用单行命令 |

Linux 和 macOS 上，新收据使用 `0600` 权限。Windows 没有相同的 POSIX 权限位，收据继承
目标目录的 DACL；应将它保存到只允许预期账户访问的目录。路径分隔符只用于命令输入，
收据结构本身不保存源路径。

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
或不可否认性。保守的 ZIP 安全限制可能拒绝体积异常大的合法 PPTX。0.1.0 是首个 alpha
版本，命令行和 Python API 在 1.0 前仍可能调整。

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

## 中文项目资料

### 项目状态

0.1.0 是 ArtifactProof 的首个 alpha 版本。收据格式已有明确约定，但 Python API 与命令行
界面在 1.0 前仍可能调整。版本发布后可从 PyPI 安装；开发或离线使用时，请选择已经审核的
源码 checkout 或核验过的 Release wheel。

项目代码从头独立实现，测试夹具全部使用合成数据，并采用 Apache-2.0 许可证。项目来源
边界见
[`PROVENANCE.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/PROVENANCE.md)，
许可正文见
[`LICENSE`](https://github.com/MaxHu-xuan/artifactproof/blob/main/LICENSE)。

## English Overview

### Is the delivered PPTX still the file that passed review?

A PPTX may pass review and then move through approval, renaming, upload,
download, and delivery. The filename may stay the same while the bytes change,
or the correct QA report may be sent with a different revision.

ArtifactProof hashes the final PPTX locally, runs basic structural checks, and
binds caller-selected external QA evidence into an HMAC-SHA256 receipt. Verify
again before delivery or after receipt to confirm that the current PPTX and
supplied evidence bytes still match that receipt.

It uploads nothing and does not rely on filenames or modification times. It is
not a general digital-signature system, a complete OOXML semantic validator,
or a judge of visual quality. Its scope is the integrity gap between basic PPTX
structure checks, external QA evidence, and the final delivery file.

### Try it in 60 seconds

Python 3.11 or newer is required. The demo needs no installation, network
access, real PPTX, or private key. It generates a one-slide synthetic deck in a
temporary directory, runs the real `create` and `verify` commands, changes the
temporary file, and confirms that verification fails.

Linux or macOS:

```bash
python3 examples/run_demo.py
```

Windows PowerShell:

```powershell
py -3 examples\run_demo.py
```

Expected output:

```json
{"evidence":"synthetic-review.json","ok":true,"operation":"generate","pptx":"synthetic-deck.pptx"}
{"ok":true,"operation":"create","qa":"pass","receipt_written":true}
{"ok":true,"operation":"verify","verified":true}
{"detected":true,"ok":true,"operation":"tamper-check"}
```

The last line means that the byte change was detected. It does not claim that
the demo deck passed visual review or reached a recipient. See
[`examples/README.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/examples/README.md)
for the generator and data boundary.
The generator never overwrites an existing path. If generation fails partway,
it may leave a synthetic output in place rather than risk deleting a path that
another process replaced concurrently.

### Which project should I use?

| Your problem | Project |
| --- | --- |
| Verify that a final PPTX and its supplied QA evidence still match the HMAC-signed receipt created after structural checks | [ArtifactProof](https://github.com/MaxHu-xuan/artifactproof) |
| After a restart, reconcile stuck tasks, timeouts, and pending delivery without guessing success | [TaskStateGuard](https://github.com/MaxHu-xuan/task-state-guard) |
| Before sharing or migrating a chat export, locally audit potential secrets, personal-data patterns, format or SQLite issues, and scan gaps | [ChatArchiveGuard](https://github.com/MaxHu-xuan/chat-archive-guard) |

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

### Use it with your own PPTX

#### 1. Install and set a signing key

Python 3.11 or newer is required. After a release is published to PyPI, install
it in an isolated virtual environment.

Linux or macOS:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install artifactproof
export ARTIFACTPROOF_SIGNING_KEY='base64:REPLACE_WITH_BASE64_KEY'
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install artifactproof
$env:ARTIFACTPROOF_SIGNING_KEY = 'base64:REPLACE_WITH_BASE64_KEY'
```

To test a development version, install from the root of a reviewed source
checkout: use `python -m pip install .` on Linux or macOS, or
`.\.venv\Scripts\python.exe -m pip install .` on Windows.

For offline use, download the wheel and `SHA256SUMS` from the same GitHub
Release. In the directory containing both files, verify the wheel with the
command for your platform.

Linux:

```bash
grep '  artifactproof-0.1.0-py3-none-any.whl$' SHA256SUMS | sha256sum --check -
```

macOS:

```bash
grep '  artifactproof-0.1.0-py3-none-any.whl$' SHA256SUMS | shasum -a 256 --check
```

Windows PowerShell:

```powershell
$wheel = '.\artifactproof-0.1.0-py3-none-any.whl'
$entry = @(Get-Content .\SHA256SUMS | Where-Object {
    $_ -match '^[0-9a-f]{64}  artifactproof-0\.1\.0-py3-none-any\.whl$'
})
if ($entry.Count -ne 1) { throw 'wheel checksum entry missing or duplicated' }
$expected = ($entry[0] -split '  ', 2)[0]
$actual = (Get-FileHash $wheel -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw 'wheel SHA-256 mismatch' }
```

After verification succeeds, install the wheel with `--no-index --no-deps`.
Do not install an unverified file merely because it has the expected name.

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
.\.venv\Scripts\python.exe -m artifactproof create deck.pptx --artifact-name approved-deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --key-id local-ci
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
.\.venv\Scripts\python.exe -m artifactproof verify deck.pptx --evidence render=render-manifest.json --receipt deck.receipt.json --expected-key-id local-ci
```

Creation and verification must use the same signing key. A successful command
returns a small JSON object. A mismatch in the PPTX, evidence, signature, or
expected key identifier returns a failure.

### Linux, macOS, and Windows command differences

The receipt format and verification result are platform-independent. The main
differences are the Python launcher, virtual-environment activation,
environment-variable syntax, and multiline command syntax.

| Action | Linux | macOS | Windows PowerShell |
| --- | --- | --- | --- |
| Start Python | `python3` | `python3` | `py -3` |
| Create a virtual environment | `python3 -m venv .venv` | `python3 -m venv .venv` | `py -3 -m venv .venv` |
| Activate it | `source .venv/bin/activate` | `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
| Set the signing key | `export ARTIFACTPROOF_SIGNING_KEY='…'` | `export ARTIFACTPROOF_SIGNING_KEY='…'` | `$env:ARTIFACTPROOF_SIGNING_KEY = '…'` |
| Split a long command | End the line with `\` | End the line with `\` | End the line with a backtick, or keep the command on one line |

New receipts use mode `0600` on Linux and macOS. Windows has no equivalent
POSIX mode bit, so the receipt inherits the destination directory's DACL; use a
directory restricted to the intended account. Path separators affect command
input only. The receipt does not store the source path.

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
PPTX. Version 0.1.0 is the initial alpha release, so the CLI and Python API may
change before 1.0.

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

Version 0.1.0 is ArtifactProof's initial alpha release. The receipt schema is
explicit, but the Python API and CLI may still change before 1.0. After a
release is published, install it from PyPI; for development or offline use,
choose a reviewed source checkout or a verified Release wheel.

This is a clean-room implementation written from scratch with synthetic test
fixtures. It is licensed under the Apache License, Version 2.0. See
[`PROVENANCE.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/PROVENANCE.md)
for the provenance boundary and
[`LICENSE`](https://github.com/MaxHu-xuan/artifactproof/blob/main/LICENSE) for
the license text.

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

[`schema/receipt.schema.json`](https://github.com/MaxHu-xuan/artifactproof/blob/main/schema/receipt.schema.json)
is a JSON Schema
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

Linux or macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Windows PowerShell:

```powershell
$previousPythonPath = $env:PYTHONPATH
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "src"
py -3 -m unittest discover -s tests -v
$env:PYTHONPATH = $previousPythonPath
```

Run the privacy-safe source-archive canonicalizer self-test:

Linux or macOS:

```bash
python3 scripts/canonicalize_sdist.py --self-test
```

Windows PowerShell:

```powershell
py -3 scripts\canonicalize_sdist.py --self-test
```

Run the values-free publication audit against the exact release tree:

Linux or macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
```

Windows PowerShell:

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
py -3 scripts\privacy_audit.py
py -3 scripts\privacy_audit.py --self-test
```

Audit an extracted source distribution with the explicit sdist profile:

Linux or macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py \
  --sdist unpacked/artifactproof-0.1.0
```

Windows PowerShell:

```powershell
py -3 scripts\privacy_audit.py --sdist unpacked\artifactproof-0.1.0
```

When running the audit copy contained inside an extracted sdist, also pass the
profile to its self-test:

Linux or macOS:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --sdist
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --sdist --self-test
```

Windows PowerShell:

```powershell
py -3 scripts\privacy_audit.py --sdist
py -3 scripts\privacy_audit.py --sdist --self-test
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

See
[`RELEASING.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/RELEASING.md)
for copyable Linux, macOS, and Windows PowerShell build and source-archive
canonicalization commands.

CI runs all supported Python versions (3.11 through 3.14) on Ubuntu, plus the
oldest and newest supported versions on macOS and Windows. Symlink tests are
skipped only when the host does not permit creating symlinks; hard-link and
path-alias checks remain active.

See
[THREAT_MODEL.md](https://github.com/MaxHu-xuan/artifactproof/blob/main/THREAT_MODEL.md),
[SECURITY.md](https://github.com/MaxHu-xuan/artifactproof/blob/main/SECURITY.md),
and [SUPPORT.md](https://github.com/MaxHu-xuan/artifactproof/blob/main/SUPPORT.md)
before embedding ArtifactProof into a delivery system.
