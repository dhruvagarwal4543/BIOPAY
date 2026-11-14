"""Build docs/FINAL_REPORT.docx and docs/FINAL_REPORT.html from docs/FINAL_REPORT.md.
Needs: pip install python-docx pillow   (kept out of requirements.txt on purpose).
PDF: node docs/html_to_pdf.mjs   (uses web/node_modules/playwright-core)."""
import html, re, sys
from pathlib import Path
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

D = Path(__file__).parent
lines = (D / "FINAL_REPORT.md").read_text().split("\n")
INLINE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")

def runs(par, text):
    for part in INLINE.split(text):
        if not part: continue
        if part.startswith("**"): r = par.add_run(part[2:-2]); r.bold = True
        elif part.startswith("`"): r = par.add_run(part[1:-1]); r.font.name = "Courier New"; r.font.size = Pt(9.5)
        else: par.add_run(part)

def inline_html(text):
    out = []
    for part in INLINE.split(text):
        if not part: continue
        if part.startswith("**"): out.append(f"<strong>{html.escape(part[2:-2])}</strong>")
        elif part.startswith("`"): out.append(f"<code>{html.escape(part[1:-1])}</code>")
        else: out.append(html.escape(part))
    return "".join(out)

def shade(par):
    pPr = par._p.get_or_add_pPr(); shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "FFF4D6"); pPr.append(shd)

doc = Document()
for s in doc.sections: s.left_margin = s.right_margin = Inches(1); s.top_margin = s.bottom_margin = Inches(0.9)
doc.styles["Normal"].font.name = "Calibri"; doc.styles["Normal"].font.size = Pt(11)
body = []  # html
i, title_done, first_h2 = 0, False, True
while i < len(lines):
    ln = lines[i]
    if not ln.strip(): i += 1; continue
    if ln.startswith("# "):
        t = ln[2:]
        for _ in range(4): doc.add_paragraph()
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = p.add_run(t); r.bold = True; r.font.size = Pt(28); r.font.color.rgb = RGBColor(0x0E, 0x76, 0x6E)
        body.append(f'<section class="cover"><h1>{html.escape(t)}</h1>'); title_done = True
    elif ln.startswith("## "):
        t = ln[3:]
        if first_h2:
            doc.add_page_break(); body.append("</section>"); first_h2 = False
        doc.add_heading(t, level=1); body.append(f"<h2>{html.escape(t)}</h2>")
    elif ln.startswith("### "):
        doc.add_heading(ln[4:], level=2); body.append(f"<h3>{html.escape(ln[4:])}</h3>")
    elif ln.startswith("!["):
        m = re.match(r"!\[(.*)\]\((.*)\)", ln); alt, src = m.group(1), m.group(2)
        doc.add_picture(str(D / src), width=Inches(6.2)); doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        c = doc.add_paragraph(); c.alignment = WD_ALIGN_PARAGRAPH.CENTER; r = c.add_run("Figure: " + alt); r.italic = True; r.font.size = Pt(9.5)
        body.append(f'<figure><img src="{src}" alt="{html.escape(alt)}"><figcaption>Figure: {html.escape(alt)}</figcaption></figure>')
    elif ln.startswith("> "):
        p = doc.add_paragraph(); runs(p, ln[2:]); shade(p); body.append(f'<blockquote>{inline_html(ln[2:])}</blockquote>')
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(set(c) <= set("- ") for c in cells): rows.append(cells)
            i += 1
        t = doc.add_table(rows=len(rows), cols=len(rows[0])); t.style = "Light Grid Accent 1"
        hb = "<table>"
        for ri, row in enumerate(rows):
            hb += "<tr>" + "".join(f"<{'th' if ri == 0 else 'td'}>{inline_html(c)}</{'th' if ri == 0 else 'td'}>" for c in row) + "</tr>"
            for ci, c in enumerate(row):
                cell = t.cell(ri, ci); cell.text = ""; runs(cell.paragraphs[0], c)
                if ri == 0:
                    for r in cell.paragraphs[0].runs: r.bold = True
        body.append(hb + "</table>"); doc.add_paragraph(); continue
    elif re.match(r"^(- |\d+\. )", ln):
        ordered = bool(re.match(r"^\d+\. ", ln)); items = []
        while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
            items.append(re.sub(r"^(- |\d+\. )", "", lines[i])); i += 1
        for it in items:
            p = doc.add_paragraph(style="List Number" if ordered else "List Bullet"); runs(p, it)
        tag = "ol" if ordered else "ul"
        body.append(f"<{tag}>" + "".join(f"<li>{inline_html(x)}</li>" for x in items) + f"</{tag}>"); continue
    else:
        # cover lines and normal paragraphs
        p = doc.add_paragraph(); runs(p, ln)
        if not title_done or first_h2: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        body.append(f"<p>{inline_html(ln)}</p>")
    i += 1
doc.save(D / "FINAL_REPORT.docx")
css = """body{font-family:Georgia,'Times New Roman',serif;color:#111;line-height:1.5;max-width:800px;margin:auto;font-size:12.5px}
.cover{text-align:center;padding-top:120px;page-break-after:always}.cover h1{font-size:34px;color:#0e766e;font-family:Helvetica,Arial,sans-serif}
h2{font-family:Helvetica,Arial,sans-serif;color:#0e766e;border-bottom:1px solid #ccc;padding-bottom:3px;margin-top:26px;page-break-after:avoid}
h3{font-family:Helvetica,Arial,sans-serif}table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border:1px solid #bbb;padding:5px 8px;text-align:left;vertical-align:top}th{background:#e6f4f2}
blockquote{background:#fff4d6;border-left:4px solid #f2b84b;margin:12px 0;padding:8px 12px}figure{margin:14px 0;text-align:center;page-break-inside:avoid}img{max-width:100%}figcaption{font-style:italic;font-size:11px;color:#444}code{font-family:Menlo,monospace;font-size:11px}"""
(D / "FINAL_REPORT.html").write_text(f'<!doctype html><html lang="en"><meta charset="utf-8"><title>BioPay Final Report</title><style>{css}</style><body>{"".join(body)}</body></html>')
print("built docx + html")
