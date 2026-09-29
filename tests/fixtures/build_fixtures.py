"""Build generated fixtures: a fictional nurse CV in Word format, plus a PDF of dense_cv.html when Chrome exists."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "scripts"))


def build_nurse_docx(out=HERE / "nurse_cv.docx", header_contact=True):
    import docx
    d = docx.Document()
    if header_contact:  # contact details in the Word header: a classic ATS trap
        d.sections[0].header.paragraphs[0].text = "jordan.lee@example.com · +44 161 496 0123"
    d.add_heading("Jordan Lee", 0)
    d.add_paragraph("Registered Nurse (Adult)")
    d.add_heading("Profile", 1)
    d.add_paragraph("NMC-registered adult nurse with six years on acute medical and elderly-care wards, "
                    "looking for a band 6 role in acute medicine.")
    d.add_heading("Experience", 1)
    table = d.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Staff Nurse (Band 5), Acute Medical Unit, Northgate General Hospital"
    table.cell(0, 1).text = "2021 – Present"
    table.cell(1, 0).text = "Staff Nurse (Band 5), Care of the Elderly, Riverside Community Hospital"
    table.cell(1, 1).text = "2018 – 2021"
    for text in ["Coordinated care for up to 8 patients per shift on a 32-bed unit.",
                 "Mentored 6 student nurses through their placements.",
                 "Led the ward's switch to electronic NEWS2 observations."]:
        d.add_paragraph(text, style="List Bullet")
    d.add_heading("Education", 1)
    d.add_paragraph("BSc (Hons) Adult Nursing, University of Salford, 2015 – 2018")
    d.add_heading("Skills", 1)
    d.add_paragraph("IV cannulation, venepuncture, NEWS2, medicines management, EPR, triage")
    d.save(out)
    return out


def build_dense_pdf(out=HERE / "dense_cv.pdf"):
    from cvlib import render_pdf
    return render_pdf(HERE / "dense_cv.html", out)


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def build_word_template_docx(out=HERE / "word_template_cv.docx"):
    """A Word-template-style CV: the contact line sits in a text box and the education entry is
    wrapped in a content control (w:sdt), as Microsoft's own CV templates do."""
    import docx
    from docx.oxml import parse_xml
    d = docx.Document()
    d.add_heading("Morgan Blake", 0)
    d.add_paragraph()._p.append(parse_xml(
        f'<w:r xmlns:w="{W_NS}" xmlns:v="urn:schemas-microsoft-com:vml"><w:pict>'
        '<v:shape style="width:300pt;height:20pt"><v:textbox><w:txbxContent><w:p><w:r>'
        '<w:t>morgan.blake@example.com · +44 20 7946 0456</w:t></w:r></w:p></w:txbxContent></v:textbox>'
        '</v:shape></w:pict></w:r>'))
    d.add_heading("Experience", 1)
    d.add_paragraph("Warehouse Supervisor, Eastfield Logistics, Mar 2021 – Present")
    heading = d.add_heading("Education", 1)
    heading._p.addnext(parse_xml(
        f'<w:sdt xmlns:w="{W_NS}"><w:sdtContent><w:p><w:r>'
        '<w:t>BTEC Level 3 Business, Eastfield College, Sep 2018 – Jun 2020</w:t></w:r></w:p></w:sdtContent></w:sdt>'))
    d.add_heading("Skills", 1)
    d.add_paragraph("Stock control, forklift licence (counterbalance), shift rota planning, SAP")
    d.save(out)
    return out


if __name__ == "__main__":
    print(build_nurse_docx())
    try:
        print(build_dense_pdf())
    except (RuntimeError, ImportError) as err:  # no browser, or cvlib not written yet (Task 2)
        print(f"skipped dense_cv.pdf: {err}")
