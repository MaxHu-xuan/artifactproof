# Security Policy

## Current status

ArtifactProof 0.1.x is an alpha-stage clean-room implementation. Do not treat it
as a complete sandbox for hostile Office documents.

| Version | Supported |
| --- | --- |
| 0.1.x | Security fixes during the alpha period |
| Earlier or unreleased snapshots | No |

## Reporting a vulnerability

Do not include real artifacts, signing keys, personal information, credentials,
or private receipts in a public issue. Use GitHub's private vulnerability
reporting for this repository:

https://github.com/MaxHu-xuan/artifactproof/security/advisories/new

If that private form is unavailable, retain the report rather than posting
sensitive details publicly. Include only the smallest synthetic reproduction,
affected version, security impact, and suggested mitigation.

The maintainer will acknowledge a usable report on a best-effort basis, assess
the impact, and coordinate a fix before public disclosure. No guaranteed
response or remediation deadline is offered for this pre-1.0 project.

## Key handling

- Generate at least 32 random bytes per environment.
- Prefer an environment value prefixed with `base64:` or `hex:`.
- Do not pass a raw key on the command line, where process listings or shell
  history may expose it.
- Give verifiers only the keys they need. Rotate by generating and switching to
  a new signing secret, and update `key_id` so verifiers can select that secret;
  changing `key_id` alone does not rotate the key.
- A receipt signature authenticates metadata; it does not encrypt the artifact
  or evidence.

## Output safety

Expected failures use stable public error codes and do not print file contents,
key material, signatures, or full input paths. Receipt metadata still includes
the key identifier, logical evidence names, and the artifact basename, so choose
non-sensitive values.

Atomic receipt files are created with mode `0600` on POSIX. On Windows, Python
mode bits do not establish a private DACL, so confidentiality depends on the
ACL of the caller-selected destination directory. Use an account-private
directory and do not assume that `0600` has Unix semantics on Windows.

## Dependency and network posture

Runtime code uses only Python's standard library and contains no network client.
Packaging tools may access a package index if a user explicitly asks them to
create an isolated build environment; normal CLI execution does not.
