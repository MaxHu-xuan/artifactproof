# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import ast
import base64
import copy
import io
import json
import os
import re
import stat
import tempfile
import unittest
import warnings
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from artifactproof import (
    ArtifactChangedError,
    InputError,
    QualityCheckError,
    ReceiptFormatError,
    SigningKeyError,
    VerificationError,
    create_receipt,
    inspect_pptx,
    load_receipt,
    parse_signing_key,
    verify_receipt,
    write_receipt,
)
from artifactproof import cli
from artifactproof import pptx as pptx_module
from artifactproof import receipt as receipt_module


KEY = b"K" * 32


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
"""

PRESENTATION = """<?xml version="1.0" encoding="UTF-8"?>
<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>
</p:presentation>
"""

PRESENTATION_RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
</Relationships>
"""

SLIDE = """<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree/></p:cSld>
</p:sld>
"""


def make_pptx(path: Path, omit=None, extra=None, overrides=None) -> None:
    parts = {
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": ROOT_RELS,
        "ppt/presentation.xml": PRESENTATION,
        "ppt/_rels/presentation.xml.rels": PRESENTATION_RELS,
        "ppt/slides/slide1.xml": SLIDE,
    }
    for name in omit or ():
        parts.pop(name, None)
    parts.update(overrides or {})
    parts.update(extra or {})
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)


class ArtifactProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.artifact = self.root / "synthetic.pptx"
        make_pptx(self.artifact)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_synthetic_pptx(self) -> None:
        result = inspect_pptx(self.artifact)
        self.assertTrue(result.passed)
        self.assertEqual(result.slide_count, 1)
        self.assertFalse(result.errors)
        self.assertTrue(all(item["status"] == "pass" for item in result.checks))

    def test_non_zip_fails_closed(self) -> None:
        invalid = self.root / "invalid.pptx"
        invalid.write_bytes(b"not a zip")
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.not_zip", result.errors)

    def test_invalid_platform_path_fails_with_stable_results(self) -> None:
        invalid_path = "PRIVATE_PATH_MARKER\x00.pptx"
        result = inspect_pptx(invalid_path)
        self.assertFalse(result.passed)
        self.assertIn("pptx.not_zip", result.errors)
        with self.assertRaises(ReceiptFormatError):
            load_receipt("PRIVATE_RECEIPT_MARKER\x00.json")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": "K" * 32}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        invalid_path,
                        "--receipt",
                        str(self.root / "receipt.json"),
                    ]
                )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, 2)
        self.assertIn("invalid_input", combined)
        self.assertNotIn("PRIVATE_PATH_MARKER", combined)

    def test_missing_required_part_fails(self) -> None:
        invalid = self.root / "missing.pptx"
        make_pptx(invalid, omit={"ppt/presentation.xml"})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.required_part_missing", result.errors)

    def test_unsafe_zip_member_fails(self) -> None:
        unsafe_names = (
            "../escape.txt",
            "C:/escape.txt",
            "C:\\escape.txt",
            "//server/share.txt",
            "ppt/./slides/slide2.xml",
            "ppt//slides/slide2.xml",
            "ppt/slides/../slide2.xml",
        )
        for index, member_name in enumerate(unsafe_names):
            with self.subTest(member_name=member_name):
                invalid = self.root / ("unsafe-" + str(index) + ".pptx")
                make_pptx(invalid, extra={member_name: "synthetic"})
                result = inspect_pptx(invalid)
                self.assertFalse(result.passed)
                self.assertIn("pptx.zip_unsafe", result.errors)

    def test_duplicate_zip_member_fails(self) -> None:
        invalid = self.root / "duplicate-member.pptx"
        make_pptx(invalid)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(invalid, "a", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("ppt/slides/slide1.xml", SLIDE)
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_encrypted_zip_member_flag_fails_before_reading(self) -> None:
        invalid = self.root / "encrypted-flag.pptx"
        make_pptx(invalid)
        package = bytearray(invalid.read_bytes())
        central_header = package.find(b"PK\x01\x02")
        self.assertNotEqual(central_header, -1)
        flags_offset = central_header + 8
        flags = int.from_bytes(package[flags_offset : flags_offset + 2], "little")
        package[flags_offset : flags_offset + 2] = (flags | 1).to_bytes(2, "little")
        invalid.write_bytes(package)
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_unsupported_zip_compression_fails_with_stable_result(self) -> None:
        invalid = self.root / "unsupported-compression.pptx"
        make_pptx(invalid)
        package = bytearray(invalid.read_bytes())
        local_header = package.find(b"PK\x03\x04")
        central_header = package.find(b"PK\x01\x02")
        self.assertNotEqual(local_header, -1)
        self.assertNotEqual(central_header, -1)
        package[local_header + 8 : local_header + 10] = (99).to_bytes(2, "little")
        package[central_header + 10 : central_header + 12] = (99).to_bytes(
            2, "little"
        )
        invalid.write_bytes(package)
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_corrupt", result.errors)

    def test_symlink_zip_member_fails(self) -> None:
        invalid = self.root / "symlink-member.pptx"
        make_pptx(invalid)
        link_info = zipfile.ZipInfo("linked-entry")
        link_info.create_system = 3
        link_info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with zipfile.ZipFile(invalid, "a") as archive:
            archive.writestr(link_info, "synthetic-target")
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_zip_member_count_limit_fails_closed(self) -> None:
        with mock.patch.object(pptx_module, "MAX_MEMBERS", 4):
            result = inspect_pptx(self.artifact)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_zip_expanded_size_limit_fails_closed(self) -> None:
        with mock.patch.object(pptx_module, "MAX_TOTAL_UNCOMPRESSED", 1):
            result = inspect_pptx(self.artifact)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_extreme_zip_compression_ratio_fails_closed(self) -> None:
        invalid = self.root / "compression-ratio.pptx"
        make_pptx(
            invalid,
            extra={"ppt/media/compressed.bin": b"A" * (1024 * 1024 + 1)},
        )
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.zip_unsafe", result.errors)

    def test_oversized_xml_part_fails_closed(self) -> None:
        with mock.patch.object(pptx_module, "MAX_XML_PART_BYTES", 1):
            result = inspect_pptx(self.artifact)
        self.assertFalse(result.passed)
        self.assertIn("pptx.xml_invalid", result.errors)

    def test_inconsistent_slide_relationship_fails(self) -> None:
        invalid = self.root / "relationship.pptx"
        broken_rels = PRESENTATION_RELS.replace("slides/slide1.xml", "slides/missing.xml")
        make_pptx(
            invalid,
            overrides={"ppt/_rels/presentation.xml.rels": broken_rels},
        )
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.slide_part_invalid", result.errors)

    def test_duplicate_numeric_slide_id_fails(self) -> None:
        invalid = self.root / "duplicate-slide-id.pptx"
        duplicate_ids = PRESENTATION.replace(
            "</p:sldIdLst>", '<p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
        )
        duplicate_rels = PRESENTATION_RELS.replace(
            "</Relationships>",
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide2.xml"/></Relationships>',
        )
        content_types = CONTENT_TYPES.replace(
            "</Types>",
            '<Override PartName="/ppt/slides/slide2.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>',
        )
        make_pptx(
            invalid,
            extra={"ppt/slides/slide2.xml": SLIDE},
            overrides={
                "[Content_Types].xml": content_types,
                "ppt/presentation.xml": duplicate_ids,
                "ppt/_rels/presentation.xml.rels": duplicate_rels,
            },
        )
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.slide_id_invalid", result.errors)

    def test_wrong_slide_content_type_fails(self) -> None:
        invalid = self.root / "content-type.pptx"
        wrong_type = CONTENT_TYPES.replace(
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
            "application/xml",
        )
        make_pptx(invalid, overrides={"[Content_Types].xml": wrong_type})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.slide_part_invalid", result.errors)

    def test_noncanonical_content_type_part_name_fails(self) -> None:
        invalid = self.root / "content-type-part-name.pptx"
        malformed = CONTENT_TYPES.replace(
            'PartName="/ppt/presentation.xml"',
            'PartName="//ppt/presentation.xml"',
        )
        make_pptx(invalid, overrides={"[Content_Types].xml": malformed})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.slide_part_invalid", result.errors)

    def test_nonstandard_relationship_uri_fails(self) -> None:
        invalid = self.root / "relationship-uri.pptx"
        fake_root_rels = ROOT_RELS.replace(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "urn:untrusted/officeDocument",
        )
        make_pptx(invalid, overrides={"_rels/.rels": fake_root_rels})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.office_relationship_invalid", result.errors)

    def test_strict_ooxml_relationship_namespace_fails_closed(self) -> None:
        invalid = self.root / "strict-ooxml.pptx"
        strict_root_rels = ROOT_RELS.replace(
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "http://purl.oclc.org/ooxml/officeDocument/relationships/officeDocument",
        )
        make_pptx(invalid, overrides={"_rels/.rels": strict_root_rels})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.office_relationship_invalid", result.errors)

    def test_strict_ooxml_presentation_namespace_fails_closed(self) -> None:
        invalid = self.root / "strict-presentation.pptx"
        strict_presentation = PRESENTATION.replace(
            "http://schemas.openxmlformats.org/presentationml/2006/main",
            "http://purl.oclc.org/ooxml/presentationml/main",
        )
        make_pptx(
            invalid,
            overrides={"ppt/presentation.xml": strict_presentation},
        )
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.xml_invalid", result.errors)

    def test_strict_ooxml_content_type_namespace_fails_closed(self) -> None:
        invalid = self.root / "strict-content-types.pptx"
        strict_content_types = CONTENT_TYPES.replace(
            "http://schemas.openxmlformats.org/package/2006/content-types",
            "http://purl.oclc.org/ooxml/package/content-types",
        )
        make_pptx(
            invalid,
            overrides={"[Content_Types].xml": strict_content_types},
        )
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.xml_invalid", result.errors)

    def test_dtd_and_entity_declarations_fail_before_xml_parse(self) -> None:
        invalid = self.root / "entity.pptx"
        entity_xml = PRESENTATION.replace(
            '<p:presentation xmlns:p=',
            '<!DOCTYPE presentation [<!ENTITY repeated "synthetic">]>\n<p:presentation xmlns:p=',
        )
        make_pptx(invalid, overrides={"ppt/presentation.xml": entity_xml})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.xml_invalid", result.errors)

    def test_utf16_dtd_cannot_bypass_entity_rejection(self) -> None:
        invalid = self.root / "utf16-entity.pptx"
        entity_xml = PRESENTATION.replace(
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<?xml version="1.0" encoding="UTF-16"?>\n'
            '<!DOCTYPE presentation [<!ENTITY repeated "synthetic">]>',
        ).encode("utf-16")
        make_pptx(invalid, overrides={"ppt/presentation.xml": entity_xml})
        result = inspect_pptx(invalid)
        self.assertFalse(result.passed)
        self.assertIn("pptx.xml_invalid", result.errors)

    def test_create_and_verify_receipt_with_evidence(self) -> None:
        evidence_path = self.root / "render.json"
        evidence_path.write_text('{"pages": 1}', encoding="utf-8")
        evidence = {"render-manifest": evidence_path}
        receipt = create_receipt(self.artifact, evidence, KEY, "test-key")
        self.assertEqual(receipt["schema_version"], "artifactproof.receipt.v1")
        self.assertEqual(receipt["qa"]["slide_count"], 1)
        self.assertEqual(receipt["signature"]["algorithm"], "HMAC-SHA256")
        self.assertTrue(
            verify_receipt(
                receipt,
                self.artifact,
                evidence,
                KEY,
                expected_key_id="test-key",
            )
        )

    def test_default_artifact_name_remains_the_source_basename(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        positional_runner_receipt = create_receipt(
            self.artifact,
            {},
            KEY,
            "test-key",
            inspect_pptx,
        )

        self.assertEqual(receipt["artifact"]["name"], self.artifact.name)
        self.assertEqual(
            positional_runner_receipt["artifact"]["name"],
            self.artifact.name,
        )

    def test_logical_artifact_name_hides_basename_and_survives_rename(self) -> None:
        source = self.root / "PRIVATE_SOURCE_BASENAME.pptx"
        make_pptx(source)
        logical_name = "approved-delivery.pptx"

        receipt = create_receipt(
            source,
            {},
            KEY,
            "test-key",
            artifact_name=logical_name,
        )
        serialized = json.dumps(receipt, ensure_ascii=False, sort_keys=True)
        self.assertEqual(receipt["artifact"]["name"], logical_name)
        self.assertNotIn(source.name, serialized)
        self.assertNotIn(str(source), serialized)

        received = self.root / "received-copy.pptx"
        source.rename(received)
        self.assertTrue(verify_receipt(receipt, received, {}, KEY))

    def test_cli_artifact_name_hides_basename_and_verifies(self) -> None:
        source = self.root / "PRIVATE_CLI_SOURCE_BASENAME.pptx"
        receipt_path = self.root / "logical-name.receipt.json"
        make_pptx(source)
        environment = {"ARTIFACTPROOF_SIGNING_KEY": "K" * 32}

        with mock.patch.dict(os.environ, environment):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                created = cli.main(
                    [
                        "create",
                        str(source),
                        "--artifact-name",
                        "approved-deck.pptx",
                        "--receipt",
                        str(receipt_path),
                        "--key-id",
                        "test-key",
                    ]
                )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                verified = cli.main(
                    [
                        "verify",
                        str(source),
                        "--receipt",
                        str(receipt_path),
                        "--expected-key-id",
                        "test-key",
                    ]
                )

        persisted = receipt_path.read_text(encoding="utf-8")
        self.assertEqual(created, 0)
        self.assertEqual(verified, 0)
        self.assertEqual(json.loads(persisted)["artifact"]["name"], "approved-deck.pptx")
        self.assertNotIn(source.name, persisted)
        self.assertNotIn(str(source), persisted)

    def test_invalid_artifact_name_fails_without_echoing_the_value(self) -> None:
        marker = "DO_NOT_ECHO_LOGICAL_NAME"
        invalid_name = "folder/" + marker

        with self.assertRaises(InputError) as captured:
            create_receipt(
                self.artifact,
                {},
                KEY,
                "test-key",
                artifact_name=invalid_name,
            )
        self.assertNotIn(marker, str(captured.exception))

        receipt_path = self.root / "invalid-name.receipt.json"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": "K" * 32}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        str(self.artifact),
                        "--artifact-name",
                        invalid_name,
                        "--receipt",
                        str(receipt_path),
                    ]
                )
        self.assertEqual(status, 2)
        self.assertFalse(receipt_path.exists())
        self.assertNotIn(marker, stdout.getvalue() + stderr.getvalue())

        for invalid in (
            "",
            ".",
            "..",
            " leading",
            "trailing ",
            "trailing.",
            "folder/name.pptx",
            "folder\\name.pptx",
            "drive:name.pptx",
            'name"quote.pptx',
            "name<left.pptx",
            "name>right.pptx",
            "name|pipe.pptx",
            "name?.pptx",
            "name*star.pptx",
            "CON",
            "con.pptx",
            "PrN.receipt",
            "AUX.txt",
            "nul.data.json",
            "COM1",
            "com9.pptx",
            "COM¹",
            "com².pptx",
            "CoM³.notes",
            "LPT1",
            "lpt9.anything",
            "LPT¹",
            "lpt².pptx",
            "LpT³.notes",
            "CON .pptx",
            "line\nbreak.pptx",
            "x" * 256,
            123,
        ):
            with self.subTest(invalid_type=type(invalid).__name__):
                with self.assertRaises(InputError) as invalid_captured:
                    create_receipt(
                        self.artifact,
                        {},
                        KEY,
                        "test-key",
                        artifact_name=invalid,
                    )
                self.assertEqual(
                    str(invalid_captured.exception),
                    "the artifact logical name is invalid",
                )

    def test_receipt_matches_schema_declared_constants_and_required_fields(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        schema_path = Path(__file__).parents[1] / "schema" / "receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], receipt["schema_version"])
        self.assertEqual(set(schema["required"]), set(receipt))
        self.assertEqual(
            schema["properties"]["qa"]["properties"]["kind"]["const"],
            receipt["qa"]["kind"],
        )
        self.assertEqual(
            schema["properties"]["signature"]["properties"]["algorithm"]["const"],
            receipt["signature"]["algorithm"],
        )

    def test_schema_timestamp_pattern_matches_runtime_syntax(self) -> None:
        schema_path = Path(__file__).parents[1] / "schema" / "receipt.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        pattern = schema["properties"]["created_at"]["pattern"]
        for created_at in (
            "2026-08-21T04:51:25Z",
            "2026-08-21T04:51:25.123456Z",
        ):
            with self.subTest(created_at=created_at):
                self.assertIsNotNone(re.fullmatch(pattern, created_at))
        for created_at in (
            "2026-08-" + "21 04:51:25Z",
            "2026-08-21T04:51:25+00:00",
            "2026-08-21T04:51:25",
            "2026-8-21T04:51:25Z",
            "2026-08-21T04:51:25.Z",
        ):
            with self.subTest(created_at=created_at):
                self.assertIsNone(re.fullmatch(pattern, created_at))

    def test_canonical_utc_receipt_timestamps_are_accepted(self) -> None:
        for created_at in (
            "2026-08-21T04:51:25Z",
            "2026-08-21T04:51:25.1Z",
            "2026-08-21T04:51:25.123456789Z",
        ):
            with self.subTest(created_at=created_at):
                receipt = create_receipt(self.artifact, {}, KEY, "test-key")
                receipt["created_at"] = created_at
                receipt["signature"]["value"] = receipt_module._signature_value(receipt, KEY)
                self.assertTrue(verify_receipt(receipt, self.artifact, {}, KEY))

    def test_noncanonical_receipt_timestamps_are_rejected(self) -> None:
        for created_at in (
            "2026-08-" + "21 04:51:25Z",
            "2026-08-21T04:51:25+00:00",
            "2026-08-21T04:51:25",
            "2026-8-21T04:51:25Z",
            "2026-08-21t04:51:25Z",
            "2026-08-21T4:51:25Z",
            "2026-08-21T04:51:25.Z",
            "2026-08-21T04:51:25z",
            "2026-02-30T04:51:25Z",
        ):
            with self.subTest(created_at=created_at):
                receipt = create_receipt(self.artifact, {}, KEY, "test-key")
                receipt["created_at"] = created_at
                receipt["signature"]["value"] = receipt_module._signature_value(receipt, KEY)
                with self.assertRaises(ReceiptFormatError):
                    verify_receipt(receipt, self.artifact, {}, KEY)

    def test_tampered_receipt_is_rejected(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        tampered = copy.deepcopy(receipt)
        tampered["qa"]["checks"][0]["detail"] = "changed-after-signing"
        with self.assertRaises(VerificationError):
            verify_receipt(tampered, self.artifact, {}, KEY)

    def test_tampered_logical_artifact_name_is_rejected(self) -> None:
        receipt = create_receipt(
            self.artifact,
            {},
            KEY,
            "test-key",
            artifact_name="approved-deck.pptx",
        )
        tampered = copy.deepcopy(receipt)
        tampered["artifact"]["name"] = "replacement-deck.pptx"

        with self.assertRaises(VerificationError):
            verify_receipt(tampered, self.artifact, {}, KEY)

    def test_tampered_key_id_is_rejected_without_expected_key_id(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "original-key")
        tampered = copy.deepcopy(receipt)
        tampered["signature"]["key_id"] = "attacker-key"
        with self.assertRaises(VerificationError):
            verify_receipt(tampered, self.artifact, {}, KEY)

    def test_signature_algorithm_is_canonicalized_and_allowlisted(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        tampered = copy.deepcopy(receipt)
        tampered["signature"]["algorithm"] = "HMAC-SHA512"
        self.assertNotEqual(
            receipt_module._canonical_payload(receipt),
            receipt_module._canonical_payload(tampered),
        )
        tampered["signature"]["value"] = receipt_module._signature_value(tampered, KEY)
        with self.assertRaises(ReceiptFormatError):
            verify_receipt(tampered, self.artifact, {}, KEY)

    def test_canonical_json_is_compact_sorted_utf8_and_order_independent(self) -> None:
        evidence_path = self.root / "evidence.txt"
        evidence_path.write_text("synthetic", encoding="utf-8")
        evidence = {"render-δ": evidence_path}
        receipt = create_receipt(self.artifact, evidence, KEY, "test-key")
        canonical = receipt_module._canonical_payload(receipt)
        payload = copy.deepcopy(receipt)
        payload["signature"].pop("value")
        expected = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(canonical, expected)
        self.assertIn("δ".encode("utf-8"), canonical)
        self.assertNotIn(b"\\u03b4", canonical)

        reordered = {
            key: copy.deepcopy(receipt[key]) for key in reversed(tuple(receipt))
        }
        reordered["artifact"] = {
            key: reordered["artifact"][key]
            for key in reversed(tuple(reordered["artifact"]))
        }
        reordered["signature"] = {
            key: reordered["signature"][key]
            for key in reversed(tuple(reordered["signature"]))
        }
        self.assertEqual(canonical, receipt_module._canonical_payload(reordered))
        self.assertTrue(verify_receipt(reordered, self.artifact, evidence, KEY))

    def test_canonical_json_rejects_non_finite_numbers(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                receipt = create_receipt(self.artifact, {}, KEY, "test-key")
                receipt["artifact"]["size_bytes"] = value
                with self.assertRaises(ReceiptFormatError):
                    receipt_module._canonical_payload(receipt)

    def test_canonical_json_rejects_non_utf8_surrogates(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        receipt["qa"]["checks"][0]["detail"] = "\ud800"
        with self.assertRaises(ReceiptFormatError):
            receipt_module._canonical_payload(receipt)

    def test_artifact_change_after_receipt_is_rejected(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        with self.artifact.open("ab") as stream:
            stream.write(b"post-qa-change")
        with self.assertRaises(VerificationError):
            verify_receipt(receipt, self.artifact, {}, KEY)

    def test_artifact_change_during_qa_is_rejected(self) -> None:
        def mutating_qa(path):
            result = inspect_pptx(path)
            with Path(path).open("ab") as stream:
                stream.write(b"mutation")
            return result

        with self.assertRaises(ArtifactChangedError):
            create_receipt(self.artifact, {}, KEY, "test-key", qa_runner=mutating_qa)

    def test_failed_qa_never_creates_a_signed_receipt(self) -> None:
        invalid = self.root / "invalid.pptx"
        invalid.write_bytes(b"synthetic invalid bytes")
        with self.assertRaises(QualityCheckError):
            create_receipt(invalid, {}, KEY, "test-key")

    def test_modified_evidence_is_rejected(self) -> None:
        evidence_path = self.root / "evidence.json"
        evidence_path.write_text("{}", encoding="utf-8")
        evidence = {"render": evidence_path}
        receipt = create_receipt(self.artifact, evidence, KEY, "test-key")
        evidence_path.write_text('{"changed": true}', encoding="utf-8")
        with self.assertRaises(VerificationError):
            verify_receipt(receipt, self.artifact, evidence, KEY)

    def test_evidence_change_during_receipt_creation_is_rejected(self) -> None:
        evidence_path = self.root / "evidence-race.json"
        evidence_path.write_text("{}", encoding="utf-8")
        real_digest = receipt_module.digest_file
        evidence_calls = 0

        def mutating_digest(path, name=None):
            nonlocal evidence_calls
            result = real_digest(path, name=name)
            if Path(path) == evidence_path:
                evidence_calls += 1
                if evidence_calls == 1:
                    evidence_path.write_text('{"changed": true}', encoding="utf-8")
            return result

        with mock.patch("artifactproof.receipt.digest_file", side_effect=mutating_digest):
            with self.assertRaises(ArtifactChangedError):
                create_receipt(
                    self.artifact,
                    {"render": evidence_path},
                    KEY,
                    "test-key",
                )

    def test_missing_and_extra_evidence_are_rejected(self) -> None:
        evidence_path = self.root / "evidence.json"
        evidence_path.write_text("{}", encoding="utf-8")
        receipt = create_receipt(self.artifact, {"render": evidence_path}, KEY, "test-key")
        with self.assertRaises(VerificationError):
            verify_receipt(receipt, self.artifact, {}, KEY)
        with self.assertRaises(VerificationError):
            verify_receipt(
                receipt,
                self.artifact,
                {"render": evidence_path, "extra": evidence_path},
                KEY,
            )

    def test_short_and_malformed_keys_are_rejected(self) -> None:
        with self.assertRaises(SigningKeyError):
            create_receipt(self.artifact, {}, b"short", "test-key")
        with self.assertRaises(SigningKeyError):
            parse_signing_key("base64:not-valid!")

    def test_encoded_key_formats(self) -> None:
        self.assertEqual(parse_signing_key("hex:" + KEY.hex()), KEY)
        encoded = base64.b64encode(KEY).decode("ascii")
        self.assertEqual(parse_signing_key("base64:" + encoded), KEY)

    def test_atomic_receipt_round_trip_and_private_mode(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        receipt_path = self.root / "receipt.json"
        write_receipt(receipt_path, receipt, protected_paths=[self.artifact])
        loaded = load_receipt(receipt_path)
        self.assertEqual(loaded, receipt)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(receipt_path.stat().st_mode), 0o600)

    def test_windows_receipt_identity_ignores_only_unstable_metadata(self) -> None:
        fields = {
            "st_dev": 1,
            "st_ino": 2,
            "st_mode": stat.S_IFREG | 0o600,
            "st_nlink": 1,
            "st_size": 3,
            "st_mtime_ns": 4,
            "st_ctime_ns": 5,
        }
        baseline = mock.Mock(**fields)
        windows_identity = receipt_module._receipt_file_identity(
            baseline, platform_name="nt"
        )
        for field in ("st_nlink", "st_ctime_ns"):
            changed = mock.Mock(**{**fields, field: fields[field] + 1})
            self.assertEqual(
                receipt_module._receipt_file_identity(changed, platform_name="nt"),
                windows_identity,
            )
            self.assertNotEqual(
                receipt_module._receipt_file_identity(changed, platform_name="posix"),
                receipt_module._receipt_file_identity(baseline, platform_name="posix"),
            )
        for field in ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns"):
            changed = mock.Mock(**{**fields, field: fields[field] + 1})
            self.assertNotEqual(
                receipt_module._receipt_file_identity(changed, platform_name="nt"),
                windows_identity,
            )

    def test_failed_atomic_replace_cleans_temporary_file(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        receipt_path = self.root / "receipt.json"
        receipt_path.write_text("previous", encoding="utf-8")
        with mock.patch(
            "artifactproof.receipt.os.replace",
            side_effect=OSError("synthetic replace failure"),
        ):
            with self.assertRaises(InputError):
                write_receipt(
                    receipt_path,
                    receipt,
                    protected_paths=[self.artifact],
                )
        self.assertEqual(receipt_path.read_text(encoding="utf-8"), "previous")
        self.assertEqual(list(self.root.glob(".artifactproof-*.tmp")), [])

    def test_receipt_destination_cannot_replace_artifact(self) -> None:
        original = self.artifact.read_bytes()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": "K" * 32}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        str(self.artifact),
                        "--receipt",
                        str(self.artifact),
                    ]
                )
        self.assertEqual(status, 2)
        self.assertEqual(self.artifact.read_bytes(), original)
        self.assertIn("invalid_input", stderr.getvalue())

    def test_receipt_destination_cannot_replace_hardlink(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        hardlink = self.root / "artifact-hardlink"
        os.link(self.artifact, hardlink)
        with self.assertRaises(InputError):
            write_receipt(hardlink, receipt, protected_paths=[self.artifact])

    def test_receipt_destination_cannot_replace_symlink_when_supported(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        symlink = self.root / "artifact-symlink"
        try:
            symlink.symlink_to(self.artifact)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")
        with self.assertRaises(InputError):
            write_receipt(symlink, receipt, protected_paths=[self.artifact])

    def test_symlink_loop_destination_fails_with_stable_input_error(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        symlink_loop = self.root / "receipt-loop"
        try:
            symlink_loop.symlink_to(symlink_loop)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")
        with self.assertRaises(InputError):
            write_receipt(
                symlink_loop,
                receipt,
                protected_paths=[self.artifact],
            )

    @unittest.skipUnless(os.name == "nt", "Windows path comparison only")
    def test_windows_case_variant_destination_alias_is_rejected(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        case_variant = Path(str(self.artifact).swapcase())
        if not case_variant.exists():
            self.skipTest("temporary directory is case-sensitive")
        with self.assertRaises(InputError):
            write_receipt(
                case_variant,
                receipt,
                protected_paths=[self.artifact],
            )

    def test_duplicate_json_keys_are_rejected(self) -> None:
        receipt_path = self.root / "duplicate-key.json"
        receipt_path.write_text(
            '{"schema_version":"artifactproof.receipt.v1",'
            '"schema_version":"artifactproof.receipt.v1"}',
            encoding="utf-8",
        )
        with self.assertRaises(ReceiptFormatError):
            load_receipt(receipt_path)

    def test_oversized_receipt_is_rejected_before_json_parsing(self) -> None:
        receipt_path = self.root / "oversized-receipt.json"
        receipt_path.write_bytes(b"{" + b" " * receipt_module.MAX_RECEIPT_BYTES)
        with mock.patch("artifactproof.receipt.json.loads") as parser:
            with self.assertRaises(ReceiptFormatError):
                load_receipt(receipt_path)
        parser.assert_not_called()

    def test_receipt_growth_between_stat_and_open_is_bounded(self) -> None:
        receipt = create_receipt(self.artifact, {}, KEY, "test-key")
        receipt_path = self.root / "growing-receipt.json"
        write_receipt(receipt_path, receipt, protected_paths=[self.artifact])
        original_size = receipt_path.stat().st_size
        real_open = receipt_module.os.open

        def grow_then_open(path, flags):
            with receipt_path.open("ab") as stream:
                stream.write(b"x")
            return real_open(path, flags)

        with (
            mock.patch.object(receipt_module, "MAX_RECEIPT_BYTES", original_size),
            mock.patch("artifactproof.receipt.os.open", side_effect=grow_then_open),
            mock.patch("artifactproof.receipt.json.loads") as parser,
        ):
            with self.assertRaises(ReceiptFormatError):
                load_receipt(receipt_path)
        parser.assert_not_called()

    def test_sensitive_input_values_are_not_output_or_persisted(self) -> None:
        artifact_content = "PRIVATE_ARTIFACT_CONTENT_MARKER"
        evidence_content = "PRIVATE_EVIDENCE_CONTENT_MARKER"
        signing_material = "PRIVATE_SIGNING_MATERIAL_" + "K" * 32
        artifact = self.root / "delivery.pptx"
        evidence_path = self.root / "PRIVATE_EVIDENCE_SOURCE.txt"
        receipt_path = self.root / "delivery.receipt.json"
        make_pptx(
            artifact,
            extra={"custom/opaque.txt": artifact_content},
        )
        evidence_path.write_text(evidence_content, encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(
            os.environ,
            {"ARTIFACTPROOF_SIGNING_KEY": signing_material},
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        str(artifact),
                        "--evidence",
                        "render-proof=" + str(evidence_path),
                        "--receipt",
                        str(receipt_path),
                        "--key-id",
                        "test-key",
                    ]
                )
        combined = stdout.getvalue() + stderr.getvalue()
        persisted = receipt_path.read_text(encoding="utf-8")
        self.assertEqual(status, 0)
        for private_value in (
            artifact_content,
            evidence_content,
            signing_material,
            str(artifact),
            str(evidence_path),
            str(receipt_path),
            evidence_path.name,
        ):
            with self.subTest(private_value=private_value):
                self.assertNotIn(private_value, combined)
                self.assertNotIn(private_value, persisted)
        stored = json.loads(persisted)
        self.assertEqual(stored["artifact"]["name"], "delivery.pptx")
        self.assertEqual(stored["evidence"][0]["name"], "render-proof")
        self.assertNotIn(stored["signature"]["value"], combined)

    def test_cli_success_does_not_disclose_key_or_paths(self) -> None:
        marker = "DO_NOT_PRINT_THIS_SIGNING_KEY_123456789"
        artifact = self.root / "PRIVATE_FILENAME_MARKER.pptx"
        receipt_path = self.root / "PRIVATE_RECEIPT_MARKER.json"
        make_pptx(artifact)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": marker}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        str(artifact),
                        "--receipt",
                        str(receipt_path),
                        "--key-id",
                        "test-key",
                    ]
                )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, 0)
        self.assertNotIn(marker, combined)
        self.assertNotIn("PRIVATE_FILENAME_MARKER", combined)
        self.assertNotIn("PRIVATE_RECEIPT_MARKER", combined)
        self.assertNotIn(receipt_path.read_text(encoding="utf-8"), combined)

    def test_cli_verify_round_trip_does_not_disclose_key_or_paths(self) -> None:
        marker = "DO_NOT_PRINT_THIS_SIGNING_KEY_123456789"
        artifact = self.root / "PRIVATE_VERIFY_FILENAME.pptx"
        receipt_path = self.root / "PRIVATE_VERIFY_RECEIPT.json"
        make_pptx(artifact)
        create_stdout = io.StringIO()
        create_stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": marker}):
            with redirect_stdout(create_stdout), redirect_stderr(create_stderr):
                self.assertEqual(
                    cli.main(
                        [
                            "create",
                            str(artifact),
                            "--receipt",
                            str(receipt_path),
                            "--key-id",
                            "verify-key",
                        ]
                    ),
                    0,
                )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "verify",
                        str(artifact),
                        "--receipt",
                        str(receipt_path),
                        "--expected-key-id",
                        "verify-key",
                    ]
                )
        combined = (
            create_stdout.getvalue()
            + create_stderr.getvalue()
            + stdout.getvalue()
            + stderr.getvalue()
        )
        self.assertEqual(status, 0)
        self.assertNotIn(marker, combined)
        self.assertNotIn("PRIVATE_VERIFY_FILENAME", combined)
        self.assertNotIn("PRIVATE_VERIFY_RECEIPT", combined)

    def test_cli_failure_does_not_disclose_key_or_file_contents(self) -> None:
        marker = "DO_NOT_PRINT_THIS_SIGNING_KEY_123456789"
        content_marker = "DO_NOT_PRINT_THIS_DOCUMENT_CONTENT"
        invalid = self.root / "private-invalid.pptx"
        receipt_path = self.root / "receipt.json"
        invalid.write_text(content_marker, encoding="utf-8")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": marker}):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = cli.main(
                    [
                        "create",
                        str(invalid),
                        "--receipt",
                        str(receipt_path),
                    ]
                )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, 2)
        self.assertNotIn(marker, combined)
        self.assertNotIn(content_marker, combined)
        self.assertNotIn(str(invalid), combined)
        self.assertIn("qa_failed", combined)
        self.assertFalse(receipt_path.exists())

    def test_unexpected_cli_failure_is_redacted_and_does_not_persist(self) -> None:
        exception_marker = "PRIVATE_INTERNAL_EXCEPTION_MARKER"
        receipt_path = self.root / "unexpected.receipt.json"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"ARTIFACTPROOF_SIGNING_KEY": "K" * 32}):
            with mock.patch(
                "artifactproof.cli.create_receipt",
                side_effect=RuntimeError(exception_marker),
            ):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    status = cli.main(
                        [
                            "create",
                            str(self.artifact),
                            "--receipt",
                            str(receipt_path),
                        ]
                    )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, 3)
        self.assertIn("internal_error", combined)
        self.assertNotIn(exception_marker, combined)
        self.assertNotIn(str(self.artifact), combined)
        self.assertNotIn(str(receipt_path), combined)
        self.assertFalse(receipt_path.exists())

    def test_argparse_error_does_not_echo_untrusted_argument(self) -> None:
        marker = "PRIVATE_UNKNOWN_ARGUMENT_MARKER"
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = cli.main(
                [
                    "create",
                    str(self.artifact),
                    "--receipt",
                    str(self.root / "receipt.json"),
                    "--unknown-option",
                    marker,
                ]
            )
        combined = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(status, 2)
        self.assertNotIn(marker, combined)
        self.assertNotIn(str(self.artifact), combined)
        self.assertIn("invalid_input", combined)

    def test_runtime_package_has_no_network_imports(self) -> None:
        package_root = Path(__file__).parents[1] / "src" / "artifactproof"
        forbidden = {"aiohttp", "http", "requests", "socket", "urllib"}
        imported = set()
        for source_path in package_root.glob("*.py"):
            tree = ast.parse(source_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".", 1)[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".", 1)[0])
        self.assertTrue(forbidden.isdisjoint(imported))


if __name__ == "__main__":
    unittest.main()
