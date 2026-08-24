#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""Generate a deterministic, fully synthetic one-slide PPTX demo."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import zipfile
from pathlib import Path
from typing import Dict, Tuple


PPTX_NAME = "synthetic-deck.pptx"
EVIDENCE_NAME = "synthetic-review.json"
ZIP_TIMESTAMP = (2000, 1, 1, 0, 0, 0)
SLIDE_MASTER_ID = "21474" + "83648"
SLIDE_LAYOUT_ID = "21474" + "83649"


def _xml(value: str) -> bytes:
    return (value.strip() + "\n").encode("utf-8")


PARTS: Dict[str, bytes] = {
    "[Content_Types].xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
          <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
          <Default Extension="xml" ContentType="application/xml"/>
          <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
          <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
          <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
          <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
          <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
          <Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>
          <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
        </Types>
        """
    ),
    "_rels/.rels": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
          <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
        </Relationships>
        """
    ),
    "docProps/app.xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
          <Application>ArtifactProof synthetic generator</Application>
          <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
          <Slides>1</Slides>
          <Notes>0</Notes>
          <HiddenSlides>0</HiddenSlides>
          <Company></Company>
          <AppVersion>1.0</AppVersion>
        </Properties>
        """
    ),
    "docProps/core.xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
          <dc:title>ArtifactProof Synthetic Demo</dc:title>
          <dc:creator>ArtifactProof synthetic generator</dc:creator>
          <cp:lastModifiedBy>ArtifactProof synthetic generator</cp:lastModifiedBy>
          <dcterms:created xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:created>
          <dcterms:modified xsi:type="dcterms:W3CDTF">2000-01-01T00:00:00Z</dcterms:modified>
        </cp:coreProperties>
        """
    ),
    "ppt/_rels/presentation.xml.rels": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/>
        </Relationships>
        """
    ),
    "ppt/presentation.xml": _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
          <p:sldMasterIdLst><p:sldMasterId id="{SLIDE_MASTER_ID}" r:id="rId1"/></p:sldMasterIdLst>
          <p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>
          <p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>
          <p:notesSz cx="6858000" cy="9144000"/>
          <p:defaultTextStyle><a:defPPr/><a:lvl1pPr marL="0" algn="l" defTabSz="914400" rtl="0" eaLnBrk="1" latinLnBrk="0" hangingPunct="1"><a:defRPr lang="en-US" sz="1800" kern="1200"/></a:lvl1pPr></p:defaultTextStyle>
        </p:presentation>
        """
    ),
    "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
        </Relationships>
        """
    ),
    "ppt/slideLayouts/slideLayout1.xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
          <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
          <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
        </p:sldLayout>
        """
    ),
    "ppt/slideMasters/_rels/slideMaster1.xml.rels": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
          <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
        </Relationships>
        """
    ),
    "ppt/slideMasters/slideMaster1.xml": _xml(
        f"""
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
          <p:cSld name="ArtifactProof Synthetic Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
          <p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>
          <p:sldLayoutIdLst><p:sldLayoutId id="{SLIDE_LAYOUT_ID}" r:id="rId1"/></p:sldLayoutIdLst>
          <p:txStyles>
            <p:titleStyle><a:lvl1pPr algn="l"><a:defRPr sz="3200" b="1"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mj-lt"/></a:defRPr></a:lvl1pPr></p:titleStyle>
            <p:bodyStyle><a:lvl1pPr marL="342900" indent="-285750"><a:defRPr sz="2000"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:bodyStyle>
            <p:otherStyle><a:defPPr/><a:lvl1pPr marL="0"><a:defRPr sz="1800"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill><a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:otherStyle>
          </p:txStyles>
        </p:sldMaster>
        """
    ),
    "ppt/slides/_rels/slide1.xml.rels": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
          <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
        </Relationships>
        """
    ),
    "ppt/slides/slide1.xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
          <p:cSld name="ArtifactProof Synthetic Demo">
            <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F4F7FB"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
            <p:spTree>
              <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
              <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
              <p:sp>
                <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                <p:spPr><a:xfrm><a:off x="762000" y="685800"/><a:ext cx="10668000" cy="1143000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
                <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" sz="2800" b="1"><a:solidFill><a:srgbClr val="17324D"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>ArtifactProof Synthetic Demo</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody>
              </p:sp>
              <p:sp>
                <p:nvSpPr><p:cNvPr id="3" name="Body"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                <p:spPr><a:xfrm><a:off x="762000" y="2057400"/><a:ext cx="10668000" cy="3429000"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="C9D6E2"/></a:solidFill></a:ln></p:spPr>
                <p:txBody><a:bodyPr lIns="304800" tIns="228600" rIns="304800" bIns="228600"/><a:lstStyle/>
                  <a:p><a:r><a:rPr lang="en-US" sz="1800"><a:solidFill><a:srgbClr val="284B63"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>Generated from fixed, public XML strings.</a:t></a:r></a:p>
                  <a:p><a:r><a:rPr lang="en-US" sz="1800"><a:solidFill><a:srgbClr val="284B63"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>Contains no personal or production data.</a:t></a:r></a:p>
                  <a:p><a:r><a:rPr lang="en-US" sz="1800"><a:solidFill><a:srgbClr val="284B63"/></a:solidFill><a:latin typeface="Arial"/></a:rPr><a:t>Demonstrates create, verify, and tamper detection.</a:t></a:r><a:endParaRPr lang="en-US"/></a:p>
                </p:txBody>
              </p:sp>
            </p:spTree>
          </p:cSld>
          <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
        </p:sld>
        """
    ),
    "ppt/theme/theme1.xml": _xml(
        """
        <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="ArtifactProof Synthetic Theme">
          <a:themeElements>
            <a:clrScheme name="ArtifactProof Synthetic">
              <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1><a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
              <a:dk2><a:srgbClr val="17324D"/></a:dk2><a:lt2><a:srgbClr val="F4F7FB"/></a:lt2>
              <a:accent1><a:srgbClr val="247BA0"/></a:accent1><a:accent2><a:srgbClr val="70C1B3"/></a:accent2><a:accent3><a:srgbClr val="B2DBBF"/></a:accent3>
              <a:accent4><a:srgbClr val="F3FFBD"/></a:accent4><a:accent5><a:srgbClr val="FF1654"/></a:accent5><a:accent6><a:srgbClr val="6C5CE7"/></a:accent6>
              <a:hlink><a:srgbClr val="0563C1"/></a:hlink><a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
            </a:clrScheme>
            <a:fontScheme name="ArtifactProof Synthetic"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
            <a:fmtScheme name="ArtifactProof Synthetic">
              <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="50000"/><a:satMod val="300000"/></a:schemeClr></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"><a:shade val="100000"/><a:satMod val="200000"/></a:schemeClr></a:gs></a:gsLst><a:lin ang="16200000" scaled="1"/></a:gradFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
              <a:lnStyleLst><a:ln w="6350" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln><a:ln w="12700" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln><a:ln w="19050" cap="flat" cmpd="sng" algn="ctr"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/><a:miter lim="800000"/></a:ln></a:lnStyleLst>
              <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
              <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"><a:tint val="95000"/><a:satMod val="170000"/></a:schemeClr></a:solidFill><a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"><a:tint val="93000"/><a:satMod val="150000"/><a:shade val="98000"/></a:schemeClr></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"><a:tint val="98000"/><a:satMod val="130000"/><a:shade val="90000"/></a:schemeClr></a:gs></a:gsLst><a:lin ang="16200000" scaled="1"/></a:gradFill></a:bgFillStyleLst>
            </a:fmtScheme>
          </a:themeElements>
        </a:theme>
        """
    ),
}


EVIDENCE = {
    "checks": [
        {"id": "demo.synthetic_source", "status": "pass"},
        {"id": "demo.no_private_data", "status": "pass"},
    ],
    "kind": "artifactproof.synthetic-demo.v1",
    "note": "Synthetic workflow evidence only; this is not a visual-review or delivery claim.",
}


class DemoGenerationError(ValueError):
    """Raised when demo files cannot be created without overwriting data."""


def pptx_bytes() -> bytes:
    """Return a byte-for-byte deterministic PPTX package."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=False,
    ) as archive:
        for name in sorted(PARTS):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 0
            info.external_attr = 0
            archive.writestr(info, PARTS[name])
    return buffer.getvalue()


def evidence_bytes() -> bytes:
    """Return deterministic synthetic evidence JSON."""

    return (
        json.dumps(EVIDENCE, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def generate_demo(output_directory: Path) -> Tuple[Path, Path]:
    """Create new demo files without replacing existing paths."""

    output_directory = Path(output_directory)
    try:
        if output_directory.is_symlink():
            raise DemoGenerationError("the demo output directory is not usable")
        output_directory.mkdir(parents=True, exist_ok=True)
        if not output_directory.is_dir():
            raise DemoGenerationError("the demo output directory is not usable")
    except OSError as exc:
        raise DemoGenerationError("the demo output directory is not usable") from exc

    destinations = (
        (output_directory / PPTX_NAME, pptx_bytes()),
        (output_directory / EVIDENCE_NAME, evidence_bytes()),
    )
    if any(path.exists() or path.is_symlink() for path, _ in destinations):
        raise DemoGenerationError("demo output already exists")

    try:
        for path, payload in destinations:
            with path.open("xb") as stream:
                stream.write(payload)
    except OSError as exc:
        raise DemoGenerationError("demo output could not be written") from exc
    return destinations[0][0], destinations[1][0]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic synthetic PPTX and evidence file."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("demo-output"))
    args = parser.parse_args()
    try:
        generate_demo(args.output_dir)
    except DemoGenerationError:
        print(
            json.dumps(
                {"error": "demo_generation_failed", "ok": False},
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "evidence": EVIDENCE_NAME,
                "ok": True,
                "operation": "generate",
                "pptx": PPTX_NAME,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
