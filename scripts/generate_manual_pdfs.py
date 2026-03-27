from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import re
import subprocess

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, Image, PageBreak, PageTemplate, Paragraph, Spacer
from reportlab.platypus.tableofcontents import TableOfContents


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "docs" / "manuals"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "pdf"
LOGO_PATH = PROJECT_ROOT / "logo.svg"
LOGO_CACHE_PATH = OUTPUT_DIR / ".assets" / "logo.png"
METADATA_PATH = SOURCE_DIR / "manual-metadata.json"

FONT_REGULAR = "ManualSans"
FONT_BOLD = "ManualSansBold"
FONT_MONO = "ManualMono"


def load_metadata() -> dict[str, str]:
    defaults = {
        "project_name": "LetoHry Lodě",
        "event_name": "Ukázkový indoor rowing závod",
        "club_name": "Doplňte název klubu nebo pořadatele",
        "contact_person": "Doplňte jméno kontaktní osoby",
        "contact_email": "Doplňte e-mail",
        "contact_phone": "Doplňte telefon",
        "document_tagline": "Provozní dokumentace pro Raspberry Pi, PM3 a závodní obsluhu",
    }
    if not METADATA_PATH.exists():
        return defaults
    loaded = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    return {**defaults, **loaded}


class ManualDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs) -> None:
        super().__init__(filename, **kwargs)
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="content")
        self.addPageTemplates([PageTemplate(id="manual", frames=[frame], onPage=self._draw_page)])

    def afterFlowable(self, flowable) -> None:
        toc_entry = getattr(flowable, "_manual_toc", None)
        if not toc_entry:
            return
        level, text, bookmark_name = toc_entry
        self.canv.bookmarkPage(bookmark_name)
        self.canv.addOutlineEntry(text, bookmark_name, level=level, closed=False)
        self.notify("TOCEntry", (level, text, self.page, bookmark_name))

    def _draw_page(self, canvas, doc) -> None:
        canvas.saveState()
        page_width, page_height = A4
        canvas.setStrokeColor(colors.HexColor("#d7dee7"))
        canvas.setLineWidth(0.6)
        canvas.line(doc.leftMargin, page_height - 14 * mm, page_width - doc.rightMargin, page_height - 14 * mm)
        canvas.line(doc.leftMargin, 12 * mm, page_width - doc.rightMargin, 12 * mm)
        canvas.setFont(FONT_REGULAR, 8.5)
        canvas.setFillColor(colors.HexColor("#516171"))
        canvas.drawString(doc.leftMargin, page_height - 11.5 * mm, "LetoHry Lodě | Provozní dokumentace")
        canvas.drawRightString(page_width - doc.rightMargin, 8 * mm, f"Strana {canvas.getPageNumber()}")
        canvas.restoreState()


def register_fonts() -> None:
    regular_path = _find_font_file("DejaVuSans.ttf")
    bold_path = _find_font_file("DejaVuSans-Bold.ttf")
    mono_path = _find_font_file("DejaVuSansMono.ttf")

    pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular_path)))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold_path)))
    pdfmetrics.registerFont(TTFont(FONT_MONO, str(mono_path)))


def _find_font_file(file_name: str) -> Path:
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / file_name,
        Path("/usr/local/share/fonts") / file_name,
        Path.home() / ".fonts" / file_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Required font file was not found: {file_name}")


def load_logo(max_width_mm: float, max_height_mm: float):
    if not LOGO_PATH.exists():
        return None

    png_logo = _prepare_logo_png()
    if png_logo is None or not png_logo.exists():
        return None

    max_width = max_width_mm * mm
    max_height = max_height_mm * mm
    with PILImage.open(png_logo) as image:
        width, height = image.size
    scale = min(max_width / width, max_height / height)
    return Image(str(png_logo), width=width * scale, height=height * scale)


def _prepare_logo_png() -> Path | None:
    LOGO_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOGO_PATH.exists():
        return None
    if LOGO_CACHE_PATH.exists() and LOGO_CACHE_PATH.stat().st_mtime >= LOGO_PATH.stat().st_mtime:
        return LOGO_CACHE_PATH

    convert_command = _find_convert_command()
    if not convert_command:
        return None

    subprocess.run([convert_command, str(LOGO_PATH), str(LOGO_CACHE_PATH)], check=True)
    return LOGO_CACHE_PATH


def _find_convert_command() -> str | None:
    for command in ("magick", "convert"):
        result = subprocess.run(["bash", "-lc", f"command -v {command} || true"], capture_output=True, text=True, check=True)
        path = result.stdout.strip()
        if path:
            return path
    return None


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ManualTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#123956"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#0f3551"),
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverSubtitle",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=13,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#516171"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CoverMeta",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4c5c6c"),
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualHeading1",
            parent=styles["Heading1"],
            fontName=FONT_BOLD,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#123956"),
            spaceBefore=10,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualHeading2",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#c95f32"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TOCHeading",
            parent=styles["Heading1"],
            fontName=FONT_BOLD,
            fontSize=19,
            leading=24,
            textColor=colors.HexColor("#123956"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualBody",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualBullet",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=14,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QuickTitle",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=23,
            leading=27,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#123956"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QuickHeading",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#c95f32"),
            spaceBefore=6,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="QuickBody",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=10,
            leading=12.5,
            alignment=TA_LEFT,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualCode",
            parent=styles["BodyText"],
            fontName=FONT_MONO,
            fontSize=9,
            leading=12,
            backColor=colors.HexColor("#f1f5f9"),
            borderPadding=6,
            spaceBefore=4,
            spaceAfter=6,
        )
    )
    return styles


def parse_markdown(text: str, styles):
    story = []
    in_code_block = False
    code_lines: list[str] = []
    heading_counters = {1: 0, 2: 0}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if line.startswith("```"):
            if in_code_block:
                code_text = "<br/>".join(_escape_xml(item) for item in code_lines)
                story.append(Paragraph(code_text, styles["ManualCode"]))
                story.append(Spacer(1, 3 * mm))
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            story.append(Spacer(1, 2 * mm))
            continue

        if line.startswith("# "):
            heading_counters[1] += 1
            heading_text = line[2:]
            paragraph = Paragraph(_escape_xml(heading_text), styles["ManualTitle"])
            paragraph._manual_toc = (0, heading_text, _bookmark_name(heading_text, heading_counters[1], 0))
            story.append(paragraph)
            story.append(Spacer(1, 4 * mm))
            continue
        if line.startswith("## "):
            heading_counters[2] += 1
            heading_text = line[3:]
            paragraph = Paragraph(_escape_xml(heading_text), styles["ManualHeading1"])
            paragraph._manual_toc = (0, heading_text, _bookmark_name(heading_text, heading_counters[2], 1))
            story.append(paragraph)
            continue
        if line.startswith("### "):
            heading_text = line[4:]
            paragraph = Paragraph(_escape_xml(heading_text), styles["ManualHeading2"])
            paragraph._manual_toc = (1, heading_text, _bookmark_name(heading_text, len(story), 2))
            story.append(paragraph)
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {_escape_xml(line[2:])}", styles["ManualBullet"]))
            continue
        if re.match(r"^\d+\. ", line):
            story.append(Paragraph(_escape_xml(line), styles["ManualBody"]))
            continue

        story.append(Paragraph(_escape_inline(line), styles["ManualBody"]))

    return story


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _escape_inline(text: str) -> str:
    escaped = _escape_xml(text)
    parts = escaped.split("`")
    if len(parts) == 1:
        return escaped
    rendered: list[str] = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            rendered.append(f"<font name='{FONT_MONO}'>{part}</font>")
        else:
            rendered.append(part)
    return "".join(rendered)


def _bookmark_name(text: str, counter: int, level: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    return f"{level}-{counter}-{slug}"


def build_cover_page(title: str, styles):
    metadata = load_metadata()
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    story = [Spacer(1, 16 * mm)]
    logo = load_logo(115, 52)
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 10 * mm))
    story.extend([
        Paragraph(metadata["project_name"], styles["CoverTitle"]),
        Paragraph(title, styles["CoverTitle"]),
        Spacer(1, 8 * mm),
        Paragraph(metadata["document_tagline"], styles["CoverSubtitle"]),
        Spacer(1, 12 * mm),
        Paragraph("Obsahuje instalační postup, uživatelskou obsluhu a pravidla závodu.", styles["CoverSubtitle"]),
        Spacer(1, 22 * mm),
        Paragraph(f"Akce: {metadata['event_name']}", styles["CoverMeta"]),
        Paragraph(f"Pořadatel / klub: {metadata['club_name']}", styles["CoverMeta"]),
        Paragraph(f"Kontakt: {metadata['contact_person']}", styles["CoverMeta"]),
        Paragraph(f"E-mail: {metadata['contact_email']} | Telefon: {metadata['contact_phone']}", styles["CoverMeta"]),
        Spacer(1, 14 * mm),
        Paragraph(f"Vygenerováno: {generated_at}", styles["CoverSubtitle"]),
        Paragraph(f"Projekt: {metadata['project_name']}", styles["CoverSubtitle"]),
        Paragraph("Dokumentace pro instalaci, provoz a organizaci závodů", styles["CoverSubtitle"]),
        PageBreak(),
    ])
    return story


def build_quick_sheet(source_file: Path, output_file: Path, title: str) -> None:
    styles = build_styles()
    text = source_file.read_text(encoding="utf-8")
    story = []
    logo = load_logo(60, 24)
    if logo is not None:
        story.append(logo)
        story.append(Spacer(1, 5 * mm))

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            story.append(Spacer(1, 1.2 * mm))
            continue
        if line.startswith("# "):
            story.append(Paragraph(_escape_xml(line[2:]), styles["QuickTitle"]))
            continue
        if line.startswith("## "):
            story.append(Paragraph(_escape_xml(line[3:]), styles["QuickHeading"]))
            continue
        if line.startswith("- "):
            story.append(Paragraph(f"• {_escape_xml(line[2:])}", styles["QuickBody"]))
            continue
        if re.match(r"^\d+\. ", line):
            story.append(Paragraph(_escape_xml(line), styles["QuickBody"]))
            continue
        story.append(Paragraph(_escape_inline(line), styles["QuickBody"]))

    doc = ManualDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="GitHub Copilot",
    )
    doc.build(story)


def build_toc(styles):
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCLevel0",
            fontName=FONT_REGULAR,
            fontSize=10.5,
            leading=13,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=3,
        ),
        ParagraphStyle(
            name="TOCLevel1",
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=12,
            leftIndent=12,
            firstLineIndent=0,
            spaceBefore=2,
        ),
    ]
    return [Paragraph("Obsah", styles["TOCHeading"]), toc, PageBreak()]


def build_pdf(source_files: list[Path], output_file: Path, title: str) -> None:
    styles = build_styles()
    story = []
    story.extend(build_cover_page(title, styles))
    story.extend(build_toc(styles))

    for index, source_file in enumerate(source_files):
        content = source_file.read_text(encoding="utf-8")
        story.extend(parse_markdown(content, styles))
        if index < len(source_files) - 1:
            story.append(PageBreak())

    doc = ManualDocTemplate(
        str(output_file),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="GitHub Copilot",
    )
    doc.build(story)


def main() -> None:
    register_fonts()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manual_files = sorted(path for path in SOURCE_DIR.glob("*.md") if path.name != "manual-metadata.json")

    for source_file in manual_files:
        output_name = source_file.stem + ".pdf"
        title = source_file.read_text(encoding="utf-8").splitlines()[0].removeprefix("# ").strip()
        if source_file.name == "04-rychly-tahak-obsluhy.md":
            build_quick_sheet(source_file, OUTPUT_DIR / output_name, title)
        else:
            build_pdf([source_file], OUTPUT_DIR / output_name, title)

    build_pdf(manual_files, OUTPUT_DIR / "00-kompletni-manualy.pdf", "LetoHry Lode - kompletni manualy")
    build_pdf(
        [SOURCE_DIR / "05-manual-pro-verejnost.md", SOURCE_DIR / "03-pravidla-zavodu.md"],
        OUTPUT_DIR / "10-manual-pro-verejnost.pdf",
        "LetoHry Lodě - informační balíček pro veřejnost",
    )
    build_pdf(
        [
            SOURCE_DIR / "01-zapojeni-a-instalace.md",
            SOURCE_DIR / "02-manual-obsluhy.md",
            SOURCE_DIR / "04-rychly-tahak-obsluhy.md",
            SOURCE_DIR / "06-interni-provozni-manual.md",
        ],
        OUTPUT_DIR / "11-interni-provozni-manual.pdf",
        "LetoHry Lodě - interní provozní manuál",
    )
    build_pdf(
        [SOURCE_DIR / "07-manual-pro-navstevniky-jednoduse.md"],
        OUTPUT_DIR / "12-jednoduchy-manual-pro-navstevniky.pdf",
        "LetoHry Lodě - jednoduchý manuál pro návštěvníky",
    )


if __name__ == "__main__":
    main()