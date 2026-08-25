# Provenance

ArtifactProof is a clean-room implementation written in a separate directory
from a behavioral specification. It intentionally excludes production source,
runtime bundles, repository history, configuration, identifiers, and data. All
test artifacts are generated synthetically at test time. The demonstration PPTX
is also generated at runtime from fixed public XML strings and fixed ZIP
metadata. No PPTX, receipt, screenshot, external review report, or production
artifact is committed as demo input.

The runtime package uses only the Python standard library. This statement is a
development record, not a legal conclusion. Before each public release, a human
maintainer must review every distributed file and confirm authorship,
authorization, and relevant third-party obligations. The project is licensed
under the Apache License, Version 2.0; see `LICENSE`.
