"""Build docs/SentinelOT-Platform-Manual.docx from docs/MANUAL.md.

This needs python-docx, which is deliberately not in requirements.txt or requirements-dev.txt:

    pip install python-docx

Run it from the repository root after editing docs/MANUAL.md:

    python scripts/build_manual.py

It reads the subset of Markdown that the manual uses (headings, paragraphs, bold, italic and
code, bullet lists, numbered lists, tables, block quotes, fenced code blocks, images), and writes
a Word file with a title page, a contents page and page numbers. The contents page is a Word
contents field: it lists the chapters when the file is built, and Word fills in the page numbers
when it opens the file and updates its fields (or when you press F9 on the contents).

The manual's "In plain words" block quotes become shaded boxes. The one Mermaid diagram becomes a
short text diagram, because Word cannot draw Mermaid.
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "MANUAL.md"
OUT = ROOT / "docs" / "SentinelOT-Platform-Manual.docx"

INK = RGBColor(0x14, 0x17, 0x1A)
ACCENT = RGBColor(0x1F, 0x3A, 0x5F)
BODY_FONT, MONO_FONT = "Calibri", "Consolas"


# --------------------------------------------------------------------------- low-level helpers

def shade(element_properties, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    element_properties.append(shd)


def set_cell_shading(cell, fill):
    shade(cell._tc.get_or_add_tcPr(), fill)


def set_cell_margins(cell, top=50, bottom=50, left=80, right=80):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def set_table_borders(table, color="8A8F94", size=4, left_thick=None):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(left_thick if (side == "left" and left_thick) else size))
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        borders.append(el)
    tblPr.append(borders)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def keep_row_together(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_field(paragraph, instruction, cached=""):
    """A complex field: begin, instruction, separate, cached text, end."""
    run = paragraph.add_run()
    for kind in ("begin",):
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
        run._r.append(el)
    run2 = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    run2._r.append(instr)
    run3 = paragraph.add_run()
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    run3._r.append(sep)
    paragraph.add_run(cached)
    run4 = paragraph.add_run()
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run4._r.append(end)


# --------------------------------------------------------------------------- inline Markdown

TOKEN = re.compile(r"(\*\*.+?\*\*|`[^`]+`|(?<!\*)\*[^*\s][^*]*?\*(?!\*))")


def add_inline(paragraph, text, size=None, bold=False, italic=False):
    """Add text with **bold**, *italic* and `code` to a paragraph."""
    for part in TOKEN.split(text):
        if not part:
            continue
        run_bold, run_italic, mono = bold, italic, False
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, run_bold = part[2:-2], True
        elif part.startswith("`") and part.endswith("`"):
            part, mono = part[1:-1], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, run_italic = part[1:-1], True
        # a bold span can hold italics: *...* inside **...**
        pieces = TOKEN.split(part) if (run_bold and "*" in part) else [part]
        for piece in pieces:
            if not piece:
                continue
            ital = run_italic
            if piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
                piece, ital = piece[1:-1], True
            run = paragraph.add_run(piece)
            run.bold = run_bold or None
            run.italic = ital or None
            if mono:
                run.font.name = MONO_FONT
                run._element.rPr.rFonts.set(qn("w:eastAsia"), MONO_FONT)
                run.font.size = Pt((size or 11) - 1)
            elif size:
                run.font.size = Pt(size)


# --------------------------------------------------------------------------- document setup

def build_styles(doc):
    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12
    for name, size, before, after in (("Heading 1", 20, 0, 10), ("Heading 2", 14, 14, 4), ("Heading 3", 12, 10, 3)):
        st = doc.styles[name]
        st.font.name = BODY_FONT
        st.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
        st.element.rPr.rFonts.set(qn("w:ascii"), BODY_FONT)
        st.element.rPr.rFonts.set(qn("w:hAnsi"), BODY_FONT)
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = ACCENT
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.left_margin = sec.right_margin = Inches(0.9)
    sec.top_margin, sec.bottom_margin = Inches(0.9), Inches(0.9)
    sec.different_first_page_header_footer = True      # no page number on the title page
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("SentinelOT Platform manual · SIMULATED · page ").font.size = Pt(9)
    add_field(footer, "PAGE", "1")
    for r in footer.runs:
        r.font.size = Pt(9)
    # have Word refresh the contents' page numbers when it opens the file
    settings = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    settings.append(upd)
    cp = doc.core_properties
    cp.title = "SentinelOT Platform: Manual"
    cp.subject = "A simulated OT security demonstration"
    cp.author = ""
    cp.keywords = "SIMULATED"


def title_page(doc, title, notice, written):
    for _ in range(5):
        doc.add_paragraph()
    p = doc.add_paragraph()
    r = p.add_run(title)
    r.bold, r.font.size, r.font.color.rgb = True, Pt(34), ACCENT
    p = doc.add_paragraph()
    r = p.add_run("A manual for the simulated plant, its 3D page, its AI triage and its alarm-limit gate")
    r.font.size, r.font.color.rgb = Pt(14), INK
    doc.add_paragraph()
    box = doc.add_table(rows=1, cols=1)
    box.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(box, color="B3261E", size=12)
    cell = box.rows[0].cells[0]
    set_cell_shading(cell, "FBEAE8")
    set_cell_margins(cell, 120, 120, 160, 160)
    cell.paragraphs[0].text = ""
    add_inline(cell.paragraphs[0], notice, size=11)
    doc.add_paragraph()
    p = doc.add_paragraph()
    add_inline(p, written, size=10)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def contents_page(doc, chapters):
    p = doc.add_paragraph()
    r = p.add_run("Contents")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(20), ACCENT
    first = True
    for i, ch in enumerate(chapters):
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(3)
        if first:
            # the field starts in the first entry and ends in the last
            begin = para.add_run()
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), "begin"); begin._r.append(el)
            ins = para.add_run()
            it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
            it.text = ' TOC \\o "1-2" \\h \\z \\u '
            ins._r.append(it)
            sep = para.add_run()
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), "separate"); sep._r.append(el)
            first = False
        para.add_run(ch)
        if i == len(chapters) - 1:
            end = para.add_run()
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), "end"); end._r.append(el)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------------------- block rendering

def column_widths(header, body, total=6.7, floor=0.6):
    """Column widths in inches, in proportion to how much text each column holds."""
    ncols = len(header)
    weights = []
    for i in range(ncols):
        cells = [header[i]] + [r[i] if i < len(r) else "" for r in body]
        lengths = sorted(len(re.sub(r"[*`]", "", c)) for c in cells)
        typical = lengths[len(lengths) * 3 // 4]          # the long-ish end, not one outlier
        weights.append(min(max(typical, 6), 60))
    scale = total / sum(weights)
    widths = [max(floor, w * scale) for w in weights]
    scale = total / sum(widths)
    return [w * scale for w in widths]


def set_widths(table, widths):
    table.autofit = False
    tblPr = table._tbl.tblPr
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    for i, w in enumerate(widths):
        table.columns[i].width = Inches(w)
        for cell in table.columns[i].cells:
            cell.width = Inches(w)


def render_table(doc, rows):
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]
    ncols = len(header)
    blank_header = not any(header)             # a two-column "field: value" table has no header
    size = 9 if ncols <= 3 else (8.5 if ncols <= 5 else 8)
    table = doc.add_table(rows=0 if blank_header else 1, cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)
    if not blank_header:
        hdr = table.rows[0]
        repeat_header(hdr)
        for i, text in enumerate(header):
            cell = hdr.cells[i]
            set_cell_shading(cell, "DCE4EE")
            set_cell_margins(cell)
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
            add_inline(cell.paragraphs[0], text, size=size, bold=True)
    for r in body:
        row = table.add_row()
        keep_row_together(row)
        for i in range(ncols):
            cell = row.cells[i]
            set_cell_margins(cell)
            if blank_header and i == 0:
                set_cell_shading(cell, "EEF1F5")
            cell.paragraphs[0].paragraph_format.space_after = Pt(0)
            add_inline(cell.paragraphs[0], r[i] if i < len(r) else "", size=size, bold=(blank_header and i == 0))
    set_widths(table, column_widths(header if not blank_header else body[0], body if not blank_header else body, 6.7,
                                    0.9 if blank_header else 0.6))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


def render_quote(doc, text):
    box = doc.add_table(rows=1, cols=1)
    box.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(box, color="1F3A5F", size=4, left_thick=24)
    cell = box.rows[0].cells[0]
    set_cell_shading(cell, "EEF3F9")
    set_cell_margins(cell, 100, 100, 160, 160)
    cell.paragraphs[0].paragraph_format.space_after = Pt(0)
    add_inline(cell.paragraphs[0], text)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def render_code(doc, lines, language):
    if language == "mermaid":
        edges = []
        for l in lines:
            m = re.search(r'(\w+)\["([^"]+)"\]\s*(-->|-\.-)\s*(?:\|"([^"]+)"\|)?\s*(\w+)(?:\["([^"]+)"\])?', l)
            if m:
                edges.append(m.groups())
        names = {}
        for l in lines:
            for k, v in re.findall(r'(\w+)\["([^"]+)"\]', l):
                names[k] = v
        lines = ["Diagram (the Markdown version draws this as a flowchart):"]
        for a, ta, kind, label, b, tb in edges:
            arrow = "--[" + label + "]-->" if label else ("-->" if kind == "-->" else "- - - (no data passes) - - -")
            lines.append(f"  {names.get(a, ta)}  {arrow}  {names.get(b, tb or b)}")
    box = doc.add_table(rows=1, cols=1)
    set_table_borders(box, color="C9CDD1", size=4)
    cell = box.rows[0].cells[0]
    set_cell_shading(cell, "F5F6F7")
    set_cell_margins(cell, 60, 60, 120, 120)
    first = True
    for l in lines:
        p = cell.paragraphs[0] if first else cell.add_paragraph()
        first = False
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run(l)
        run.font.name = MONO_FONT
        run._element.rPr.rFonts.set(qn("w:eastAsia"), MONO_FONT)
        run.font.size = Pt(9)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def render_image(doc, alt, path, figure_no):
    full = (SRC.parent / path).resolve()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    width = Inches(2.6) if "phone" in path else Inches(6.0)
    p.add_run().add_picture(str(full), width=width)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_inline(cap, f"Figure {figure_no}. {alt}", size=9, italic=True)


# --------------------------------------------------------------------------- main

def main():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    doc = Document()
    build_styles(doc)

    # front matter
    title = lines[0].lstrip("# ").strip()
    i = 1
    paras = []
    while not lines[i].startswith("## "):
        if lines[i].strip():
            paras.append(lines[i].strip())
        i += 1
    chapters = [re.sub(r"^## ", "", l) for l in lines if re.match(r"^## \d+\. ", l)]
    title_page(doc, title, paras[0], paras[1])
    contents_page(doc, chapters)

    figure_no = 0
    in_contents = False
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("## "):
            heading = stripped[3:]
            in_contents = heading == "Contents"
            if in_contents:
                i += 1
                continue
            if re.match(r"^\d+\. ", heading) or heading == "How to read this manual":
                if doc.paragraphs and doc.paragraphs[-1].text.strip() != "" or True:
                    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            doc.add_heading(heading, level=1)
            i += 1
            continue
        if in_contents:
            i += 1
            continue
        if stripped.startswith("### "):
            doc.add_heading(stripped[4:], level=2)
            i += 1
            continue
        if stripped == "---" or not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            language = stripped[3:].strip()
            block = []
            i += 1
            while not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            render_code(doc, block, language)
            i += 1
            continue
        if stripped.startswith("|"):
            block = []
            while i < n and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            render_table(doc, block)
            continue
        if stripped.startswith(">"):
            block = []
            while i < n and lines[i].strip().startswith(">"):
                block.append(lines[i].strip().lstrip(">").strip())
                i += 1
            render_quote(doc, " ".join(b for b in block if b))
            continue
        m = re.match(r"^!\[(.*)\]\((.+)\)$", stripped)
        if m:
            figure_no += 1
            render_image(doc, m.group(1), m.group(2), figure_no)
            i += 1
            continue
        m = re.match(r"^- (.*)$", stripped)
        if m:
            while i < n and re.match(r"^- ", lines[i].strip()):
                p = doc.add_paragraph(style="List Bullet")
                p.paragraph_format.space_after = Pt(3)
                add_inline(p, lines[i].strip()[2:])
                i += 1
            continue
        m = re.match(r"^(\d+)\. (.*)$", stripped)
        if m:
            while i < n and re.match(r"^\d+\. ", lines[i].strip()):
                num, text = re.match(r"^(\d+)\. (.*)$", lines[i].strip()).groups()
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.35)
                p.paragraph_format.first_line_indent = Inches(-0.25)
                p.paragraph_format.space_after = Pt(3)
                add_inline(p, f"{num}.  {text}")
                i += 1
            continue
        # a plain paragraph: gather the lines until a blank line or another block starts
        block = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(r"^(#|\||>|```|- |\d+\. |!\[|---)", lines[i].strip()):
            block.append(lines[i].strip())
            i += 1
        p = doc.add_paragraph()
        add_inline(p, " ".join(block))

    doc.save(OUT)
    print("wrote", OUT.relative_to(ROOT), "|", figure_no, "figures |", len(doc.tables), "tables")


if __name__ == "__main__":
    sys.exit(main())
