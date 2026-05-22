from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/Noto Sans SC.ttf"),
    Path("C:/Windows/Fonts/NotoSansSC-Medium.otf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
]


def find_font() -> Path | None:
    return next((path for path in FONT_CANDIDATES if path.exists()), None)


def build_pdf(report: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    font_path = find_font()
    if font_path:
        try:
            _build_reportlab_pdf(report, output_path, font_path)
            if has_embedded_font(output_path):
                return output_path
        except Exception:
            pass
    _build_image_pdf(report, output_path, font_path)
    return output_path


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_reportlab_pdf(report: dict, output_path: Path, font_path: Path) -> None:
    pdfmetrics.registerFont(TTFont("BriefCJK", str(font_path)))
    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "BriefBase",
        parent=styles["Normal"],
        fontName="BriefCJK",
        fontSize=9.5,
        leading=14,
        wordWrap="CJK",
        spaceAfter=4,
    )
    title = ParagraphStyle("BriefTitle", parent=base, fontSize=18, leading=24, spaceAfter=8)
    subtitle = ParagraphStyle(
        "BriefSubtitle",
        parent=base,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=12,
    )
    section = ParagraphStyle("BriefSection", parent=base, fontSize=12, leading=16, spaceBefore=8)
    item_title = ParagraphStyle("BriefItemTitle", parent=base, fontSize=11, leading=15, spaceBefore=9)
    small = ParagraphStyle(
        "BriefSmall",
        parent=base,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#475569"),
    )

    story = [
        Paragraph(_escape(report.get("title", "科技快报")), title),
        Paragraph(_escape(report.get("subtitle", "")), subtitle),
        Paragraph("本期导读", section),
        Paragraph(_escape(report.get("overview", "")), base),
    ]

    sources = report.get("checked_sources") or []
    if sources:
        story.append(Paragraph("已检查来源类别", section))
        story.append(Paragraph(_escape("、".join(sources)), small))

    for index, entry in enumerate(report.get("entries", []), 1):
        story.append(Paragraph(f"{index}. {_escape(entry.get('title', '未命名更新'))}", item_title))
        for label, key in [
            ("是什么", "what"),
            ("主要作用", "purpose"),
            ("核心功能", "features"),
            ("对比", "comparison"),
            ("适合谁", "who"),
        ]:
            value = entry.get(key)
            if value:
                story.append(Paragraph(f"<b>{label}:</b> {_escape(value)}", base))
        link = entry.get("link")
        if link:
            story.append(Paragraph("<b>直达链接:</b>", base))
            urls = _split_links(link)
            for number, url in enumerate(urls, 1):
                label = "打开原文" if len(urls) == 1 else f"打开原文 {number}"
                story.append(
                    Paragraph(
                        f'<link href="{_escape(url)}" color="blue"><u>{_escape(label)}</u></link>',
                        base,
                    )
                )
        story.append(Spacer(1, 3 * mm))

    if report.get("footer"):
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(_escape(report["footer"]), small))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)


def _page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("BriefCJK", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def has_embedded_font(path: Path) -> bool:
    reader = PdfReader(str(path))
    for page in reader.pages:
        resources = page.get("/Resources")
        if hasattr(resources, "get_object"):
            resources = resources.get_object()
        fonts = resources.get("/Font") if resources else {}
        if hasattr(fonts, "get_object"):
            fonts = fonts.get_object()
        for font_ref in (fonts or {}).values():
            font = font_ref.get_object() if hasattr(font_ref, "get_object") else font_ref
            descriptor = font.get("/FontDescriptor")
            if descriptor:
                descriptor = descriptor.get_object() if hasattr(descriptor, "get_object") else descriptor
                if any(key in descriptor for key in ["/FontFile", "/FontFile2", "/FontFile3"]):
                    return True
            descendants = font.get("/DescendantFonts")
            if descendants:
                for descendant in descendants:
                    obj = descendant.get_object() if hasattr(descendant, "get_object") else descendant
                    descriptor = obj.get("/FontDescriptor")
                    if descriptor:
                        descriptor = descriptor.get_object() if hasattr(descriptor, "get_object") else descriptor
                        if any(key in descriptor for key in ["/FontFile", "/FontFile2", "/FontFile3"]):
                            return True
    return False


def _split_links(value: str) -> list[str]:
    return [part.strip() for part in str(value).replace("\r", "\n").split("\n") if part.strip()]


def _flatten_report(report: dict) -> list[str]:
    lines = [report.get("title", "科技快报"), report.get("subtitle", ""), "", "本期导读", report.get("overview", "")]
    if report.get("checked_sources"):
        lines += ["", "已检查来源类别", "、".join(report["checked_sources"])]
    for index, entry in enumerate(report.get("entries", []), 1):
        lines += ["", f"{index}. {entry.get('title', '未命名更新')}"]
        for label, key in [
            ("是什么", "what"),
            ("主要作用", "purpose"),
            ("核心功能", "features"),
            ("对比", "comparison"),
            ("适合谁", "who"),
            ("直达链接", "link"),
        ]:
            if entry.get(key):
                lines.append(f"{label}: {entry[key]}")
    if report.get("footer"):
        lines += ["", report["footer"]]
    return lines


def _build_image_pdf(report: dict, output_path: Path, font_path: Path | None) -> None:
    font_path = font_path or find_font()
    if not font_path:
        raise RuntimeError("No CJK font found for image PDF fallback.")

    page_w, page_h = 1240, 1754
    margin = 80
    y = margin
    font = ImageFont.truetype(str(font_path), 30)
    title_font = ImageFont.truetype(str(font_path), 46)
    small_font = ImageFont.truetype(str(font_path), 25)
    pages: list[Image.Image] = []
    image = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(image)

    def add_page() -> None:
        nonlocal image, draw, y
        pages.append(image)
        image = Image.new("RGB", (page_w, page_h), "white")
        draw = ImageDraw.Draw(image)
        y = margin

    for raw_line in _flatten_report(report):
        current_font = title_font if raw_line == report.get("title") else small_font if raw_line.startswith("http") else font
        wrapped = _wrap_line(raw_line, draw, current_font, page_w - 2 * margin)
        for line in wrapped:
            if y > page_h - margin:
                add_page()
            draw.text((margin, y), line, fill=(17, 24, 39), font=current_font)
            y += current_font.size + 16
        y += 8

    pages.append(image)
    first, rest = pages[0], pages[1:]
    first.save(output_path, save_all=True, append_images=rest, resolution=160)


def _wrap_line(line: str, draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if not line:
        return [""]
    chunks = textwrap.wrap(line, width=42, break_long_words=True, replace_whitespace=False)
    result: list[str] = []
    for chunk in chunks or [line]:
        current = ""
        for char in chunk:
            trial = current + char
            if draw.textlength(trial, font=font) <= max_width:
                current = trial
            else:
                if current:
                    result.append(current)
                current = char
        if current:
            result.append(current)
    return result
