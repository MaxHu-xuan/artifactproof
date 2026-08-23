# SPDX-License-Identifier: Apache-2.0

"""Public, non-sensitive error types for ArtifactProof."""


class ArtifactProofError(Exception):
    """Base class whose message is safe to display to a CLI user."""

    code = "artifactproof_error"
    default_message = "artifact verification failed"

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class InputError(ArtifactProofError):
    code = "invalid_input"
    default_message = "an input file or argument is invalid"


class SigningKeyError(ArtifactProofError):
    code = "invalid_signing_key"
    default_message = "the signing key is missing, malformed, or too short"


class QualityCheckError(ArtifactProofError):
    code = "qa_failed"

    def __init__(self, error_codes=None):
        codes = tuple(error_codes or ())
        message = "PPTX quality checks failed"
        if codes:
            message += ": " + ",".join(codes)
        super().__init__(message)
        self.error_codes = codes


class ArtifactChangedError(ArtifactProofError):
    code = "artifact_changed"
    default_message = "the artifact changed during or after QA"


class ReceiptFormatError(ArtifactProofError):
    code = "invalid_receipt"
    default_message = "the receipt has an invalid or unsupported shape"


class VerificationError(ArtifactProofError):
    code = "verification_failed"
    default_message = "the receipt, artifact, or evidence did not verify"
