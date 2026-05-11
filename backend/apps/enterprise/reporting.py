import html
import io
import zipfile
from datetime import datetime


def make_pdf(title, rows):
    lines = [title, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ""]
    lines.extend([f"{label}: {value}" for label, value in rows])
    escaped = []
    y = 780
    for line in lines[:42]:
        escaped_line = str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        escaped.append(f"BT /F1 10 Tf 48 {y} Td ({escaped_line}) Tj ET")
        y -= 18
    stream = "\n".join(escaped).encode("utf-8")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    payload = io.BytesIO()
    payload.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(payload.tell())
        payload.write(f"{index} 0 obj\n".encode("ascii"))
        payload.write(obj)
        payload.write(b"\nendobj\n")
    xref = payload.tell()
    payload.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    payload.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        payload.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.write(f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return payload.getvalue()


def _sheet_xml(headers, rows):
    body = []
    all_rows = [headers, *rows]
    for row_number, row in enumerate(all_rows, start=1):
        cells = []
        for col_number, value in enumerate(row, start=1):
            col = chr(64 + col_number)
            text = html.escape(str(value))
            cells.append(f'<c r="{col}{row_number}" t="inlineStr"><is><t>{text}</t></is></c>')
        body.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{"".join(body)}</sheetData>
</worksheet>'''


def make_xlsx(headers, rows):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        archive.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        archive.writestr("xl/workbook.xml", """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets>
</workbook>""")
        archive.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(headers, rows))
    return output.getvalue()
