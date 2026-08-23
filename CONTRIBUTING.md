# Contributing

Thank you for helping improve ArtifactProof.

By intentionally submitting a contribution for inclusion in this project, you
agree that it is provided under the Apache License, Version 2.0, on the same
terms as the project. Submit only work that you have the right to contribute.

Use synthetic, non-sensitive fixtures. Do not submit credentials, signing keys,
private receipts, production artifacts, personal information, customer data,
internal identifiers, private paths, logs, databases, or repository history.
Sanitize test output and issue reports before sharing them publicly.

Run the local tests before opening a contribution:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/privacy_audit.py --self-test
```

Update documentation and tests for every behavior change. Platform-sensitive
changes must state the intended Linux, macOS, and Windows behavior. Avoid new
runtime dependencies unless the security and offline-use tradeoff is explicit.

Use a focused pull request and complete the repository's safety checklist.
Maintainers may decline changes that expand the threat model beyond the
project's current scope.

Security vulnerabilities should be reported according to `SECURITY.md`, without
including sensitive samples in a public issue.
