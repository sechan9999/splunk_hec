from app.ai.gateway import AIGateway
from app.rag.ingest import ingest_document
from app.rag.service import answer
from app.security.rbac import principals_for


def test_gateway_fake_provider_responds():
    gw = AIGateway(default_provider="fake")
    out = gw.chat([{"role": "user", "content": "hello"}])
    assert out["provider"] == "fake"
    assert "fake-llm" in out["content"]


def test_rag_answer_is_grounded_and_cited(session):
    ingest_document(session, title="Return Policy", acl=[],
                    content="returns accepted within 30 days with receipt and original packaging")
    session.commit()
    result = answer("what is the return window", role="sales", k=3)
    assert result["trimmed"] is True
    assert result["citations"]
    assert result["citations"][0]["title"] == "Return Policy"
    assert "grounded" in result["answer"]  # fake provider marks grounded context


def test_rag_answer_excludes_out_of_scope_citations(session):
    ingest_document(session, title="Board Minutes", acl=["grp:manager"],
                    content="confidential board minutes acquisition strategy budget")
    session.commit()
    result = answer("acquisition strategy budget", role="sales", k=5)
    assert all(c["title"] != "Board Minutes" for c in result["citations"])
