"""Génération de fichiers Office simples (sans dépendance) : .docx (WordprocessingML
minimal avec styles de titres) et .xlsx (via openpyxl)."""
import io
import zipfile
from xml.sax.saxutils import escape

_CT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_FONT = '<w:rFonts w:ascii="Montserrat" w:hAnsi="Montserrat" w:cs="Arial"/>'
_BLUE = "1F3A8A"


def _style(sid, name, size, bold=False, color=None, before=0, after=120):
    rpr = _FONT + ("<w:b/>" if bold else "") + (f'<w:color w:val="{color}"/>' if color else "") + \
        f'<w:sz w:val="{size}"/>'
    return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/>'
            f'<w:basedOn w:val="Normal"/><w:qFormat/>'
            f'<w:pPr><w:keepNext/><w:spacing w:before="{before}" w:after="{after}"/></w:pPr><w:rPr>{rpr}</w:rPr></w:style>')


_STYLES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}>'
           f'<w:docDefaults><w:rPrDefault><w:rPr>{_FONT}<w:sz w:val="20"/><w:lang w:val="fr-FR"/></w:rPr></w:rPrDefault>'
           '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
           + _style("Title", "Title", 36, True, _BLUE, 0, 80)
           + _style("Subtitle", "Subtitle", 20, False, "6B7280", 0, 240)
           + _style("Heading1", "heading 1", 26, True, _BLUE, 280, 120)
           + _style("Heading2", "heading 2", 22, True, "111827", 200, 80)
           + '</w:styles>')


def _para(kind, text):
    style = {"title": "Title", "subtitle": "Subtitle", "h1": "Heading1", "h2": "Heading2"}.get(kind)
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    if kind == "li":
        ppr = '<w:pPr><w:ind w:left="360" w:hanging="240"/></w:pPr>'
        text = "• " + text
    runs = []
    for i, line in enumerate(text.split("\n")):
        if i:
            runs.append("<w:r><w:br/></w:r>")
        runs.append(f'<w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r>')
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def _table(rows, widths=None):
    grid = ""
    if widths:
        grid = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{w}"/>' for w in widths) + "</w:tblGrid>"
    cells = []
    for i, row in enumerate(rows):
        tcs = []
        for j, v in enumerate(row):
            tcw = f'<w:tcW w:w="{widths[j]}" w:type="dxa"/>' if widths else ""
            shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{_BLUE}"/>' if i == 0 else ""
            rpr = '<w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>' if i == 0 else ""
            tcs.append(f'<w:tc><w:tcPr>{tcw}{shade}</w:tcPr><w:p><w:r>{rpr}'
                       f'<w:t xml:space="preserve">{escape(str(v))}</w:t></w:r></w:p></w:tc>')
        hdr = "<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>" if i == 0 else "<w:trPr><w:cantSplit/></w:trPr>"
        cells.append(f"<w:tr>{hdr}{''.join(tcs)}</w:tr>")
    border = "".join(f'<w:{b} w:val="single" w:sz="4" w:color="D1D5DB"/>'
                     for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    layout = '<w:tblLayout w:type="fixed"/>' if widths else ""
    return (f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders>{layout}</w:tblPr>'
            f"{grid}{''.join(cells)}</w:tbl><w:p/>")


def docx(blocks, landscape=False, font_size=10):
    """blocks : liste de (type, contenu), type ∈ title, subtitle, h1, h2, p, li, table
    (contenu d'une table : liste de lignes, la première étant l'en-tête ; ou
    (lignes, largeurs en twips) pour des colonnes fixes)."""
    body = "".join((_table(*c) if isinstance(c, tuple) else _table(c)) if k == "table" else _para(k, c)
                   for k, c in blocks)
    size = '<w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>' if landscape else '<w:pgSz w:w="11906" w:h="16838"/>'
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W}><w:body>{body}'
                f'<w:sectPr>{size}'
                '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/>'
                '</w:sectPr></w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CT)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/_rels/document.xml.rels", _DOC_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", _STYLES.replace('<w:sz w:val="20"/><w:lang', f'<w:sz w:val="{font_size * 2}"/><w:lang'))
    return buf.getvalue()


def xlsx(sheets):
    """sheets : liste de (nom de feuille, lignes) ; la première ligne est l'en-tête."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets:
        ws = wb.create_sheet(name[:31])
        for row in rows:
            ws.append(list(row))
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=_BLUE)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            for c in col[1:]:
                c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
