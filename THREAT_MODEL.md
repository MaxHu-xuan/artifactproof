# Threat Model

## Protected assets

- Integrity of the delivered artifact and declared evidence.
- Authenticity of the receipt under a caller-controlled HMAC key.
- Confidentiality of signing keys and artifact contents in CLI output.
- Availability of the verifier when inspecting malformed PPTX packages.

## Trust boundaries

The artifact, PPTX ZIP metadata, XML parts, evidence files, receipt file and CLI
paths are untrusted. The local Python interpreter, operating system, caller,
signing key and installed ArtifactProof code are trusted.

## Addressed threats

- Artifact replacement after QA is detected by digest verification.
- Mutation while QA runs is detected by comparing pre-QA and post-QA digests.
- Receipt edits are detected by HMAC verification over canonical JSON.
- Signature algorithm and key identifier are covered by the HMAC; only the
  signature value itself is excluded from canonicalization.
- Missing, extra, renamed or modified evidence is rejected.
- Receipt destinations that alias artifacts or evidence by normalized path,
  symlink or hard link are rejected by the writer.
- ZIP traversal names, duplicate members, encrypted members, symlinks, excessive
  member counts, excessive expanded size and extreme compression ratios are
  rejected before XML parsing.
- Receipt files larger than 1 MiB are rejected before JSON parsing.
- Receipt reads are size-bounded and compare file identity before and after the
  read, including across the metadata-check/open boundary.
- Malformed or inconsistent core PPTX relationships fail closed.
- Only strict UTF-8 XML is accepted; DTD and entity declarations are forbidden
  before XML parsing. This intentionally rejects otherwise valid UTF-16 OOXML
  in exchange for a standard-library-only entity-expansion boundary.
- Expected CLI failures do not echo file contents or signing keys.

## Out of scope and residual risks

- HMAC cannot distinguish two parties that share the same key. Public
  verifiability requires a future asymmetric-signature profile.
- Files can still change after receipt creation and before delivery. A delivery
  integration must verify immediately before opening or sending the file.
- Filesystem races cannot be eliminated portably with path-only APIs. The hasher
  checks file identity and metadata before and after each read, but a hostile
  local process with sufficient privileges remains outside the trust model.
- POSIX `0600` modes are not Windows ACLs. On Windows, receipt confidentiality
  relies on the destination directory's inherited ACL, and file-identity fields
  exposed by Python may be less discriminating on some filesystems.
- Basic XML/relationship validation is not full ECMA-376 or OPC conformance.
- The checker does not expand external relationships, execute macros, render
  slides, inspect embedded objects, or determine whether content is safe.
- Compression limits are conservative heuristics, not a proof against all denial
  of service techniques.
- Receipt filenames, key identifiers, artifact names and logical evidence names
  are metadata and may be sensitive. `--artifact-name` can replace the default
  source basename, but the caller must still choose a non-sensitive label.
- HMAC signatures provide integrity and authenticity, not confidentiality,
  timestamp authority, non-repudiation, or proof of channel delivery.
