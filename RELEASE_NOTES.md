# ArtifactProof v0.1.0

## 中文版本说明

发布日期：2026-08-25。

### 这个版本解决什么问题

ArtifactProof 帮助团队确认最终交付的 PowerPoint 文件，是否仍是完成基础结构检查并与指定
外部质检证据建立关联的那一份 PPTX。它在本地为 PPTX 和证据文件计算摘要，生成
HMAC-SHA256 收据，并在交付前或接收后重新验证这些字节是否仍与收据一致。

它的能力边界比通用数字签名系统或完整 OOXML 验证器更窄。ArtifactProof 不判断幻灯片
设计、可访问性、事实准确性、恶意内容或文件是否真实送达。渲染报告、人工验收记录和
其他外部报告可以作为证据绑定，但工具不会独立证明这些报告的结论正确。

### 0.1.0 包含的功能

- 提供离线 `create` 和 `verify` 命令，并返回适合自动化处理的稳定 JSON 结果。
- 使用 SHA-256 标识 PPTX 和每个具名证据文件的准确字节内容。
- 使用调用方提供的共享密钥生成 HMAC-SHA256 收据。
- 对 PPTX 的 ZIP 容器、XML、必要部件和基础关系执行保守检查。
- 在创建收据期间检测 PPTX 或证据被其他进程修改的情况。
- 原子写入收据，并在预期失败时返回不回显输入值的稳定错误。
- 允许调用方使用中性的逻辑名称，避免把敏感源文件名写入收据。
- 在 Linux 上覆盖 Python 3.11 至 3.14，并在 macOS 和 Windows 上覆盖 Python 3.11
  与 3.14。
- 提供完全使用合成数据、结果可复现的 PPTX 演示，覆盖创建、验证和篡改检测。
- 提供源码树、源码包和发布制品隐私检查，以及可复现的源码包规范化流程。

### 安装与快速验证

需要 Python 3.11 或更高版本。对于已经发布到 PyPI 的版本，建议安装在独立虚拟环境中。

Linux 或 macOS：

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install artifactproof
artifactproof --version
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install artifactproof
.\.venv\Scripts\python.exe -m artifactproof --version
```

如需在安装前查看核心流程，可在已经审核的源码 checkout 根目录运行合成演示：

Linux 或 macOS：

```bash
python3 examples/run_demo.py
```

Windows PowerShell：

```powershell
py -3 examples\run_demo.py
```

演示只创建临时合成文件，并使用明确公开、只供演示的固定密钥。该密钥不能用于真实
收据。离线安装时，请从同一个 GitHub Release 获取 wheel 与 `SHA256SUMS`。在包含这两个
文件的目录中，先运行与你的平台对应的 SHA-256 核验命令。

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

核验通过后安装 wheel：

Linux 或 macOS：

```bash
python -m pip install --no-index --no-deps ./artifactproof-0.1.0-py3-none-any.whl
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps .\artifactproof-0.1.0-py3-none-any.whl
```

不要仅凭文件名安装未经核验或来源不明的 wheel。

### 平台与安全边界

- 收据格式在 Linux、macOS 和 Windows 上保持一致。
- Linux 和 macOS 上的新收据使用 `0600` 权限；Windows 上的收据继承目标目录的
  DACL，应存放在仅允许预期账户访问的目录中。
- 0.1.0 内置支持 Transitional OOXML `.pptx`，保守的安全限制可能拒绝体积异常大但
  结构合法的文件。
- HMAC 验证要求双方通过可信渠道获得同一把密钥；它不提供公开验证、签名者身份或
  不可否认性。
- 0.1.0 是首个 alpha 版本，命令行和 Python API 在 1.0 前仍可能调整。

### 发布完整性

维护者按
[`RELEASING.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/RELEASING.md)
审核准确的发布内容。GitHub Release 应恰好包含五个上传资产：`SOURCE_COMMIT`、
`SHA256SUMS`、CycloneDX 1.6 SBOM、wheel 和规范化 sdist；缺少或增加上传资产都会被发布
工作流拒绝。GitHub 为 tag 自动生成的 `Source code (zip)` 和 `Source code (tar.gz)` 下载项
不是上传资产，不计入这五项。`SHA256SUMS` 只记录 wheel、规范化 sdist 和 SBOM 的摘要，
并作为源码包之外的独立资产发布，避免校验值反过来改变它所描述的源码包。

通过五个上传资产、来源提交、摘要、SBOM 身份、源码包规范化、隐私检查和离线安装验证后，
工作流只把 wheel 与规范化 sdist 送入 PyPI 发布阶段。每次发布前，维护者必须确认 GitHub
已配置受保护的 `pypi` environment，并确认 PyPI Trusted Publishing 已注册匹配的仓库、
工作流和环境；发布任务使用短期 OIDC 身份，不需要保存长期 PyPI API token。

---

## English release notes

Release date: 2026-08-25.

### What this release is for

ArtifactProof helps a team confirm that a delivered PowerPoint file is still
the same PPTX that passed basic structural checks and was associated with
selected external QA evidence. It hashes the PPTX and evidence locally, creates
an HMAC-SHA256 receipt, and later verifies that the current bytes still match
that receipt.

Its scope is deliberately narrower than a general digital-signature system or
a complete OOXML validator. ArtifactProof does not judge slide design,
accessibility, factual accuracy, malicious content, or successful delivery.
Rendering reports, human review records, and other external reports can be
bound as evidence, but the tool does not independently validate their
conclusions.

### Included in 0.1.0

- Offline `create` and `verify` commands with stable JSON results for
  automation.
- SHA-256 identity for the exact PPTX bytes and every named evidence file.
- HMAC-SHA256 receipts using a caller-supplied shared key.
- Conservative checks for the PPTX ZIP container, XML, required parts, and
  basic relationships.
- Detection of PPTX or evidence changes while a receipt is being created.
- Atomic receipt writes and stable expected-error output that does not echo
  input values.
- A caller-selected logical artifact name for keeping a sensitive source
  basename out of the receipt.
- Python 3.11 through 3.14 coverage on Linux, plus Python 3.11 and 3.14 coverage
  on macOS and Windows.
- A deterministic, fully synthetic PPTX demo covering creation, verification,
  and tamper detection.
- Privacy checks for the source tree, source archive, and release artifacts,
  together with reproducible source-archive canonicalization.

### Install and verify the release

Python 3.11 or newer is required. After a release is published to PyPI, install
it in an isolated virtual environment.

Linux or macOS:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install artifactproof
artifactproof --version
```

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install artifactproof
.\.venv\Scripts\python.exe -m artifactproof --version
```

To inspect the core workflow before installation, run the synthetic demo
from the root of a reviewed source checkout.

Linux or macOS:

```bash
python3 examples/run_demo.py
```

Windows PowerShell:

```powershell
py -3 examples\run_demo.py
```

The demo creates only temporary synthetic files and uses an explicitly public
key intended for demonstration. Never reuse that key for a real receipt. For
offline installation, obtain the wheel and `SHA256SUMS` from the same GitHub
Release. In the directory containing both files, first run the SHA-256 check
for your platform.

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

After verification succeeds, install the wheel.

Linux or macOS:

```bash
python -m pip install --no-index --no-deps ./artifactproof-0.1.0-py3-none-any.whl
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --no-deps .\artifactproof-0.1.0-py3-none-any.whl
```

Do not install an unverified wheel merely because it has the expected name.

### Platform and security boundaries

- The receipt format is the same on Linux, macOS, and Windows.
- New receipts use mode `0600` on Linux and macOS. On Windows, receipts inherit
  the destination directory's DACL and should be stored in a directory limited
  to the intended account.
- Version 0.1.0 has built-in support for Transitional OOXML `.pptx` files.
  Conservative safety limits may reject an unusually large but structurally
  valid package.
- HMAC verification requires both sides to obtain the same secret through a
  trusted channel. It does not provide public verification, signer identity,
  or non-repudiation.
- Version 0.1.0 is the initial alpha release, so the CLI and Python API may
  change before 1.0.

### Release integrity

Maintainers review the exact release contents by following every step in
[`RELEASING.md`](https://github.com/MaxHu-xuan/artifactproof/blob/main/RELEASING.md).
A GitHub Release should contain exactly five uploaded assets: `SOURCE_COMMIT`,
`SHA256SUMS`, the CycloneDX 1.6 SBOM, the wheel, and the canonical sdist. The
release workflow rejects missing or additional uploaded assets. GitHub's
automatically generated `Source code (zip)` and `Source code (tar.gz)` downloads
are not uploaded assets and are not counted among the five. `SHA256SUMS` records
the wheel, canonical sdist, and SBOM hashes outside the source archive so that
recording a checksum cannot change the archive it describes.

After the workflow verifies the five uploaded assets, source commit, hashes, SBOM
identity, canonical sdist, privacy gates, and offline installation, only the
wheel and canonical sdist enter the PyPI publishing stage. Before each release,
maintainers must ensure that a protected GitHub `pypi` environment is configured
and that the matching repository, workflow, and environment are registered in
PyPI Trusted Publishing. The publishing job then uses short-lived OIDC identity
without storing a long-lived PyPI API token.
