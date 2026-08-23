# SPDX-License-Identifier: Apache-2.0

"""Offline, hash-bound QA receipts for generated artifacts."""

from .errors import (
    ArtifactChangedError,
    ArtifactProofError,
    InputError,
    QualityCheckError,
    ReceiptFormatError,
    SigningKeyError,
    VerificationError,
)
from .pptx import PptxQAResult, inspect_pptx
from .receipt import (
    create_receipt,
    load_receipt,
    parse_signing_key,
    signing_key_from_env,
    verify_receipt,
    write_receipt,
)

__version__ = "0.1.0"

__all__ = [
    "ArtifactChangedError",
    "ArtifactProofError",
    "InputError",
    "PptxQAResult",
    "QualityCheckError",
    "ReceiptFormatError",
    "SigningKeyError",
    "VerificationError",
    "create_receipt",
    "inspect_pptx",
    "load_receipt",
    "parse_signing_key",
    "signing_key_from_env",
    "verify_receipt",
    "write_receipt",
]
