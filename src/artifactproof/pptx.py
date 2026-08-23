# SPDX-License-Identifier: Apache-2.0

"""Dependency-free, conservative structural checks for PPTX packages."""

from __future__ import annotations

import posixpath
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple, Union
from xml.etree import ElementTree


PathLike = Union[str, Path]

MAX_MEMBERS = 5000
MAX_TOTAL_UNCOMPRESSED = 256 * 1024 * 1024
MAX_XML_PART_BYTES = 8 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200

CONTENT_TYPES = "[Content_Types].xml"
ROOT_RELS = "_rels/.rels"
PRESENTATION = "ppt/presentation.xml"
PRESENTATION_RELS = "ppt/_rels/presentation.xml.rels"

P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

OFFICE_DOCUMENT_RELATIONSHIP_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
}
SLIDE_RELATIONSHIP_TYPES = {
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
}
PRESENTATION_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
SLIDE_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
)
FORBIDDEN_XML_DECLARATION = re.compile(
    r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE
)
XML_DECLARATION_ENCODING = re.compile(
    r"^\s*<\?xml\b[^>]*\bencoding\s*=\s*(['\"])([^'\"]+)\1",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PptxQAResult:
    kind: str
    passed: bool
    slide_count: int
    checks: Tuple[Dict[str, str], ...]
    errors: Tuple[str, ...]
    warnings: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "kind": self.kind,
            "passed": self.passed,
            "slide_count": self.slide_count,
            "checks": [dict(item) for item in self.checks],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _result(
    checks: List[Dict[str, str]],
    errors: List[str],
    slide_count: int = 0,
) -> PptxQAResult:
    return PptxQAResult(
        kind="pptx-basic",
        passed=not errors,
        slide_count=slide_count,
        checks=tuple(checks),
        errors=tuple(errors),
        warnings=tuple(),
    )


def _check(
    checks: List[Dict[str, str]],
    check_id: str,
    passed: bool,
    detail: Optional[str] = None,
) -> None:
    item = {"id": check_id, "status": "pass" if passed else "fail"}
    if detail:
        item["detail"] = detail
    checks.append(item)


def _safe_member_name(name: str) -> bool:
    if not name or "\\" in name or name.startswith("/"):
        return False
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        return False
    trimmed = name[:-1] if name.endswith("/") else name
    if not trimmed:
        return False
    path = PurePosixPath(trimmed)
    if any(part in ("", ".", "..") for part in path.parts):
        return False
    if path.parts and ":" in path.parts[0]:
        return False
    return posixpath.normpath(trimmed) == trimmed


def _normalized_target(base_directory: str, target: str) -> Optional[str]:
    if not target or "\\" in target:
        return None
    if target.startswith("/"):
        target = target[1:]
        base_directory = ""
    normalized = posixpath.normpath(posixpath.join(base_directory, target))
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        return None
    if not _safe_member_name(normalized):
        return None
    return normalized


def _content_type_part_name(value: str) -> Optional[str]:
    if not value.startswith("/") or value.startswith("//"):
        return None
    member = value[1:]
    if member.endswith("/") or not _safe_member_name(member):
        return None
    return member


def _parse_xml(archive: zipfile.ZipFile, member: str) -> ElementTree.Element:
    info = archive.getinfo(member)
    if info.file_size > MAX_XML_PART_BYTES:
        raise ValueError("xml_part_too_large")
    content = archive.read(member)
    if b"\x00" in content:
        raise ValueError("xml_encoding_forbidden")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("xml_encoding_forbidden") from exc
    encoding_match = XML_DECLARATION_ENCODING.search(decoded)
    if encoding_match and encoding_match.group(2).lower().replace("_", "-") not in {
        "utf-8",
        "utf8",
    }:
        raise ValueError("xml_encoding_forbidden")
    if FORBIDDEN_XML_DECLARATION.search(decoded):
        raise ValueError("xml_dtd_forbidden")
    return ElementTree.fromstring(content)


def _relationship_elements(root: ElementTree.Element) -> List[ElementTree.Element]:
    if root.tag != "{%s}Relationships" % PKG_REL_NS:
        raise ValueError("invalid_relationship_root")
    return list(root.findall("{%s}Relationship" % PKG_REL_NS))


def inspect_pptx(path: PathLike) -> PptxQAResult:
    """Inspect core package and slide relationships without extracting files."""

    checks: List[Dict[str, str]] = []
    errors: List[str] = []
    try:
        archive = zipfile.ZipFile(Path(path), "r")
    except (OSError, ValueError, zipfile.BadZipFile):
        errors.append("pptx.not_zip")
        _check(checks, "zip.container", False)
        return _result(checks, errors)

    try:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        unsafe = len(infos) > MAX_MEMBERS or len(names) != len(set(names))
        total_uncompressed = 0
        for info in infos:
            total_uncompressed += info.file_size
            mode = (info.external_attr >> 16) & 0xFFFF
            is_symlink = stat.S_IFMT(mode) == stat.S_IFLNK
            encrypted = bool(info.flag_bits & 0x1)
            ratio_too_high = False
            if info.file_size > 1024 * 1024:
                if info.compress_size == 0:
                    ratio_too_high = True
                else:
                    ratio_too_high = (
                        info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
                    )
            if (
                not _safe_member_name(info.filename)
                or is_symlink
                or encrypted
                or ratio_too_high
            ):
                unsafe = True
        if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
            unsafe = True
        _check(checks, "zip.safety", not unsafe)
        if unsafe:
            errors.append("pptx.zip_unsafe")
            return _result(checks, errors)

        try:
            bad_member = archive.testzip()
        # Decompressor backends expose different Exception subclasses across
        # methods, Python versions and operating systems. Any read failure is
        # an integrity failure; BaseException controls are still allowed out.
        except Exception:
            bad_member = "corrupt"
        _check(checks, "zip.integrity", bad_member is None)
        if bad_member is not None:
            errors.append("pptx.zip_corrupt")
            return _result(checks, errors)

        required = {CONTENT_TYPES, ROOT_RELS, PRESENTATION, PRESENTATION_RELS}
        required_ok = required.issubset(set(names))
        _check(checks, "package.required_parts", required_ok)
        if not required_ok:
            errors.append("pptx.required_part_missing")
            return _result(checks, errors)

        try:
            content_types = _parse_xml(archive, CONTENT_TYPES)
            root_rels = _parse_xml(archive, ROOT_RELS)
            presentation = _parse_xml(archive, PRESENTATION)
            presentation_rels = _parse_xml(archive, PRESENTATION_RELS)
        except (ElementTree.ParseError, KeyError, ValueError, RuntimeError):
            errors.append("pptx.xml_invalid")
            _check(checks, "package.core_xml", False)
            return _result(checks, errors)

        core_xml_ok = (
            content_types.tag == "{%s}Types" % CT_NS
            and presentation.tag == "{%s}presentation" % P_NS
        )
        _check(checks, "package.core_xml", core_xml_ok)
        if not core_xml_ok:
            errors.append("pptx.xml_invalid")
            return _result(checks, errors)

        try:
            root_relationships = _relationship_elements(root_rels)
            office_targets = []
            for relation in root_relationships:
                relation_type = relation.attrib.get("Type", "")
                if relation_type in OFFICE_DOCUMENT_RELATIONSHIP_TYPES:
                    if relation.attrib.get("TargetMode") == "External":
                        office_targets.append(None)
                    else:
                        office_targets.append(
                            _normalized_target("", relation.attrib.get("Target", ""))
                        )
            office_ok = office_targets == [PRESENTATION]
        except ValueError:
            office_ok = False
        _check(checks, "package.office_document", office_ok)
        if not office_ok:
            errors.append("pptx.office_relationship_invalid")
            return _result(checks, errors)

        slide_ids = presentation.findall("{%s}sldIdLst/{%s}sldId" % (P_NS, P_NS))
        slide_count = len(slide_ids)
        numeric_slide_ids = [item.attrib.get("id", "") for item in slide_ids]
        _check(
            checks,
            "presentation.has_slides",
            slide_count > 0,
            "slide_count=%d" % slide_count,
        )
        if slide_count == 0:
            errors.append("pptx.no_slides")
            return _result(checks, errors)
        slide_ids_ok = all(value.isdigit() for value in numeric_slide_ids) and len(
            numeric_slide_ids
        ) == len(set(numeric_slide_ids))
        _check(checks, "presentation.slide_ids", slide_ids_ok)
        if not slide_ids_ok:
            errors.append("pptx.slide_id_invalid")
            return _result(checks, errors, slide_count)

        try:
            relation_items = _relationship_elements(presentation_rels)
        except ValueError:
            errors.append("pptx.slide_relationship_invalid")
            _check(checks, "presentation.slide_relationships", False)
            return _result(checks, errors, slide_count)

        slide_relations: Dict[str, str] = {}
        all_relation_ids = [relation.attrib.get("Id", "") for relation in relation_items]
        invalid_relation = (
            not all(all_relation_ids)
            or len(all_relation_ids) != len(set(all_relation_ids))
        )
        for relation in relation_items:
            if relation.attrib.get("Type", "") in SLIDE_RELATIONSHIP_TYPES:
                relation_id = relation.attrib.get("Id", "")
                if (
                    not relation_id
                    or relation_id in slide_relations
                    or relation.attrib.get("TargetMode") == "External"
                ):
                    invalid_relation = True
                    continue
                target = _normalized_target("ppt", relation.attrib.get("Target", ""))
                if target is None:
                    invalid_relation = True
                    continue
                slide_relations[relation_id] = target

        requested_rel_ids = [item.attrib.get("{%s}id" % R_NS, "") for item in slide_ids]
        targets = [slide_relations.get(relation_id) for relation_id in requested_rel_ids]
        relations_ok = (
            not invalid_relation
            and all(requested_rel_ids)
            and len(requested_rel_ids) == len(set(requested_rel_ids))
            and all(targets)
            and len(targets) == len(set(targets))
        )
        _check(checks, "presentation.slide_relationships", relations_ok)
        if not relations_ok:
            errors.append("pptx.slide_relationship_invalid")
            return _result(checks, errors, slide_count)

        override_items = content_types.findall("{%s}Override" % CT_NS)
        override_names = [
            _content_type_part_name(item.attrib.get("PartName", ""))
            for item in override_items
        ]
        invalid_override = any(
            name is None or not item.attrib.get("ContentType", "")
            for name, item in zip(override_names, override_items)
        )
        valid_override_names = [name for name in override_names if name is not None]
        duplicate_override = len(valid_override_names) != len(
            set(valid_override_names)
        )
        content_overrides = {
            name: item.attrib.get("ContentType", "")
            for name, item in zip(override_names, override_items)
            if name is not None
        }
        slide_parts_ok = (
            not invalid_override
            and not duplicate_override
            and content_overrides.get(PRESENTATION) == PRESENTATION_CONTENT_TYPE
        )
        for target in targets:
            if (
                not target.startswith("ppt/slides/")
                or not target.endswith(".xml")
                or target not in names
                or content_overrides.get(target) != SLIDE_CONTENT_TYPE
            ):
                slide_parts_ok = False
                break
            try:
                slide_root = _parse_xml(archive, target)
            except (ElementTree.ParseError, KeyError, ValueError, RuntimeError):
                slide_parts_ok = False
                break
            if slide_root.tag != "{%s}sld" % P_NS:
                slide_parts_ok = False
                break
        _check(checks, "presentation.slide_parts", slide_parts_ok)
        if not slide_parts_ok:
            errors.append("pptx.slide_part_invalid")

        return _result(checks, errors, slide_count)
    finally:
        archive.close()
