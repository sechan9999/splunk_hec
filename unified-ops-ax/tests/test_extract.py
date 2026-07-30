"""Binary extraction tests. docx/pdf fixtures are synthesized in-memory with
no third-party writer, so the suite stays offline and deterministic."""
import io
import zipfile

import httpx

from app.connectors.extract import extract_text, is_extractable
from app.connectors.graph_client import GraphAuth, GraphClient
from app.connectors.sharepoint import SharePointConnector


def make_pdf(text: str) -> bytes:
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode("latin-1") + b") Tj ET"
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = b"%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(out)
    n = len(objs) + 1
    out += b"xref\n0 " + str(n).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer\n<< /Size " + str(n).encode() + b" /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF"
    return out


def make_docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", xml)
    return buf.getvalue()


# --- unit -------------------------------------------------------------------
def test_is_extractable_covers_binary_formats():
    assert is_extractable("report.docx")
    assert is_extractable("manual.pdf")
    assert not is_extractable("photo.png")


def test_extract_pdf():
    assert extract_text("a.pdf", make_pdf("Hello RAG PDF")) == "Hello RAG PDF"


def test_extract_docx_paragraphs_and_tables():
    text = extract_text("a.docx", make_docx(["Intro line", "Second line"]))
    assert text == "Intro line\nSecond line"


def test_corrupt_binaries_return_none_not_raise():
    assert extract_text("bad.pdf", b"not a pdf") is None
    assert extract_text("bad.docx", b"not a zip") is None


# --- connector end-to-end (docx over Graph) ---------------------------------
def test_connector_extracts_docx_with_acl():
    docx_bytes = make_docx(["Quarterly production defect summary", "Root cause and countermeasure"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        path = request.url.path
        if path == "/v1.0/sites/site1/drives":
            return httpx.Response(200, json={"value": [{"id": "drv1"}]})
        if path == "/v1.0/drives/drv1/items/root/children":
            return httpx.Response(200, json={"value": [
                {"id": "d1", "name": "defects.docx", "file": {}, "size": len(docx_bytes), "webUrl": "https://sp/d1"}]})
        if path == "/v1.0/drives/drv1/items/d1/content":
            return httpx.Response(200, content=docx_bytes)
        if path == "/v1.0/drives/drv1/items/d1/permissions":
            return httpx.Response(200, json={"value": [{"grantedToV2": {"group": {"id": "production"}}}]})
        return httpx.Response(404, json={})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    auth = GraphAuth("t", "c", "s", login_base_url="https://login.microsoftonline.com", http=http)
    conn = SharePointConnector(GraphClient(auth, base_url="https://graph.microsoft.com/v1.0", http=http), "site1")

    docs = conn.list_documents()
    assert len(docs) == 1
    assert docs[0].title == "defects.docx"
    assert "defect summary" in docs[0].content
    assert "countermeasure" in docs[0].content
    assert docs[0].acl == ["grp:production"]
