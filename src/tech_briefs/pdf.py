from __future__ import annotations

import re
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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/Noto Sans SC.ttf"),
    Path("C:/Windows/Fonts/NotoSansSC-Medium.otf"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"),
    Path("/usr/share/fonts/truetype/droid/DroidSansFallback.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
]

INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#64748b")
BLUE = colors.HexColor("#2563eb")
LIGHT_BLUE = colors.HexColor("#eff6ff")
PAPER = colors.HexColor("#f8fafc")
BORDER = colors.HexColor("#dbe3ef")
ASCII_RUN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:;/\\'\"()\[\]{}_\-+#%&=!?@|~]*")
CHINESE_DIGITS = "零一二三四五六七八九"


def find_font() -> Path | None:
    return next((path for path in FONT_CANDIDATES if path.exists()), None)


def build_pdf(report: dict, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    expected_links = _expected_link_count(report)
    errors: list[str] = []

    for attempt, (font_path, subfont_index) in enumerate(_font_attempts(), 1):
        font_name = f"BriefCJK{attempt}"
        try:
            _build_reportlab_pdf(report, output_path, font_path, font_name, subfont_index)
            embedded = has_embedded_font(output_path)
            link_count = count_uri_annotations(output_path)
            if embedded and link_count >= expected_links:
                return output_path
            errors.append(f"{font_path}#{subfont_index}: embedded={embedded}, links={link_count}/{expected_links}")
        except Exception as exc:
            errors.append(f"{font_path}#{subfont_index}: {type(exc).__name__}: {exc}")

    if expected_links:
        detail = "; ".join(errors[-8:]) if errors else "no candidate CJK fonts found"
        raise RuntimeError(
            "Could not build a vector PDF with clickable links. "
            "Refusing to fall back to image PDF because image PDFs lose links. "
            f"Attempts: {detail}"
        )

    font_path = find_font()
    _build_image_pdf(report, output_path, font_path)
    return output_path


def _font_attempts() -> list[tuple[Path, int]]:
    attempts: list[tuple[Path, int]] = []
    for path in FONT_CANDIDATES:
        if not path.exists():
            continue
        max_subfonts = 6 if path.suffix.lower() in {".ttc", ".otc"} else 1
        attempts.extend((path, index) for index in range(max_subfonts))
    return attempts


def _escape(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rich(value: object) -> str:
    text = str(value)
    parts: list[str] = []
    cursor = 0
    for match in ASCII_RUN_RE.finditer(text):
        parts.append(_escape(text[cursor : match.start()]))
        parts.append(f'<font name="Helvetica">{_escape(match.group(0))}</font>')
        cursor = match.end()
    parts.append(_escape(text[cursor:]))
    return "".join(parts)


def _build_reportlab_pdf(report: dict, output_path: Path, font_path: Path, font_name: str, subfont_index: int) -> None:
    pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=subfont_index))
    styles = _styles(font_name)
    page_width = A4[0] - 32 * mm

    story: list = [
        _header_block(report, page_width, styles),
        Spacer(1, 5 * mm),
        _info_block("本期导读", report.get("overview", ""), styles, page_width),
    ]

    sources = report.get("checked_sources") or []
    if sources:
        story.append(Spacer(1, 3 * mm))
        story.append(_source_block(sources, styles, page_width))

    story.append(Spacer(1, 4 * mm))
    for index, entry in enumerate(report.get("entries", []), 1):
        story.append(KeepTogether([_entry_card(index, entry, styles, page_width)]))
        story.append(Spacer(1, 4 * mm))

    if report.get("footer"):
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(_rich(report["footer"]), styles["small"]))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    doc.build(
        story,
        onFirstPage=lambda canvas, doc: _page_number(canvas, doc, font_name),
        onLaterPages=lambda canvas, doc: _page_number(canvas, doc, font_name),
    )


def _styles(font_name: str) -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    base = ParagraphStyle(
        "BriefBase",
        parent=sample["Normal"],
        fontName=font_name,
        fontSize=9.4,
        leading=13.6,
        textColor=INK,
        wordWrap="CJK",
        splitLongWords=1,
        spaceAfter=3,
    )
    return {
        "base": base,
        "title": ParagraphStyle("BriefTitle", parent=base, fontSize=21, leading=27, textColor=colors.white),
        "subtitle": ParagraphStyle(
            "BriefSubtitle",
            parent=base,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#dbeafe"),
        ),
        "section": ParagraphStyle("BriefSection", parent=base, fontSize=11.5, leading=15, textColor=INK),
        "item_title": ParagraphStyle("BriefItemTitle", parent=base, fontSize=12.6, leading=16.5, textColor=INK),
        "meta": ParagraphStyle("BriefMeta", parent=base, fontSize=7.8, leading=10.5, textColor=MUTED),
        "label": ParagraphStyle("BriefLabel", parent=base, fontSize=8.4, leading=11.5, textColor=BLUE),
        "small": ParagraphStyle("BriefSmall", parent=base, fontSize=8.2, leading=11.5, textColor=MUTED),
        "link": ParagraphStyle("BriefLink", parent=base, fontSize=7.8, leading=10.8, textColor=BLUE, splitLongWords=1),
    }


def _header_block(report: dict, width: float, styles: dict[str, ParagraphStyle]) -> Table:
    content = [
        Paragraph(_rich(report.get("title", "科技快报")), styles["title"]),
        Paragraph(_rich(report.get("subtitle", "")), styles["subtitle"]),
    ]
    table = Table([[content]], colWidths=[width])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1d4ed8")),
                ("BOX", (0, 0), (-1, -1), 0.25, colors.HexColor("#1e40af")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 11),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )
    return table


def _info_block(title: str, body: str, styles: dict[str, ParagraphStyle], width: float) -> Table:
    table = Table(
        [
            [Paragraph(f"<b>{_rich(title)}</b>", styles["section"])],
            [Paragraph(_rich(body), styles["base"])],
        ],
        colWidths=[width],
    )
    table.setStyle(_soft_table_style())
    return table


def _source_block(sources: list[str], styles: dict[str, ParagraphStyle], width: float) -> Table:
    text = "、".join(sources)
    return _info_block("已检查来源", text, styles, width)


def _entry_card(index: int, entry: dict, styles: dict[str, ParagraphStyle], width: float) -> Table:
    rows: list[list] = []
    title = f"{index}. {entry.get('title', '未命名更新')}"
    meta = " | ".join(
        part
        for part in [
            f"来源: {entry.get('source', '未知')}",
            f"类型: {entry.get('type', '更新')}",
            f"主题: {entry.get('topic', '科技')}",
            f"时间: {entry.get('published', '')}",
            f"分数: {entry.get('score', '')}",
        ]
        if not part.endswith(": ")
    )
    rows.append([Paragraph(f"<b>{_rich(title)}</b>", styles["item_title"])])
    rows.append([Paragraph(_rich(meta), styles["meta"])])

    for label, key in [
        ("是什么", "what"),
        ("主要作用", "purpose"),
        ("核心功能", "features"),
        ("对比判断", "comparison"),
        ("适合谁", "who"),
    ]:
        value = entry.get(key)
        if value:
            rows.append([_label_value(label, value, styles)])

    urls = _split_links(entry.get("link", ""))
    if urls:
        link_lines = []
        for number, url in enumerate(urls, 1):
            prefix = "直达链接" if len(urls) == 1 else f"直达链接 {number}"
            link_lines.append(
                Paragraph(
                    f'<b>{_rich(prefix)}:</b> '
                    f'<link href="{_escape(url)}" color="blue"><u><font name="Helvetica">{_escape(url)}</font></u></link>',
                    styles["link"],
                )
            )
        rows.append([link_lines])

    table = Table(rows, colWidths=[width], splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.35, BORDER),
                ("LINEBEFORE", (0, 0), (0, -1), 3.0, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 5.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _label_value(label: str, value: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table(
        [[Paragraph(f"<b>{_rich(label)}</b>", styles["label"]), Paragraph(_rich(value), styles["base"])]],
        colWidths=[22 * mm, None],
    )
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def _soft_table_style() -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#bfdbfe")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )


def _page_number(canvas, doc, font_name: str) -> None:
    canvas.saveState()
    canvas.setFont(font_name, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"第 {_chinese_number(doc.page)} 页")
    canvas.restoreState()


def _chinese_number(value: int) -> str:
    if value < 10:
        return CHINESE_DIGITS[value]
    if value < 20:
        return "十" + (CHINESE_DIGITS[value % 10] if value % 10 else "")
    if value < 100:
        tens, ones = divmod(value, 10)
        return CHINESE_DIGITS[tens] + "十" + (CHINESE_DIGITS[ones] if ones else "")
    return str(value)


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


def count_uri_annotations(path: Path) -> int:
    reader = PdfReader(str(path))
    count = 0
    for page in reader.pages:
        for annot_ref in page.get("/Annots") or []:
            annot = annot_ref.get_object()
            action = annot.get("/A")
            if action and action.get("/URI"):
                count += 1
    return count


def _expected_link_count(report: dict) -> int:
    return sum(len(_split_links(entry.get("link", ""))) for entry in report.get("entries", []))


def _split_links(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").replace("\r", "\n").split("\n") if part.strip()]


def _flatten_report(report: dict) -> list[str]:
    lines = [report.get("title", "科技快报"), report.get("subtitle", ""), "", "本期导读", report.get("overview", "")]
    if report.get("checked_sources"):
        lines += ["", "已检查来源", "、".join(report["checked_sources"])]
    for index, entry in enumerate(report.get("entries", []), 1):
        lines += ["", f"{index}. {entry.get('title', '未命名更新')}"]
        for label, key in [
            ("是什么", "what"),
            ("主要作用", "purpose"),
            ("核心功能", "features"),
            ("对比判断", "comparison"),
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
