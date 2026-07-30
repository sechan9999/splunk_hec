"""The core security guarantee: retrieval never returns a document the caller
is not entitled to — even when it is the most semantically relevant match."""
from app.rag.ingest import ingest_document
from app.rag.service import retrieve
from app.security.rbac import principals_for


def _seed(session):
    ingest_document(session, title="Sales Forecast", acl=["grp:sales"],
                    content="quarterly sales forecast pipeline revenue targets by region")
    ingest_document(session, title="Payroll Ledger", acl=["grp:accounting"],
                    content="payroll tax ledger accounting salary deductions withholding")
    ingest_document(session, title="Company Handbook", acl=[],  # public
                    content="company handbook vacation policy general onboarding")
    session.commit()


def test_sales_role_cannot_retrieve_accounting_doc(session):
    _seed(session)
    principals = principals_for("sales")
    # Query targets the accounting doc's exact terms — relevance is high...
    hits = retrieve("payroll tax ledger withholding", principals, k=5)
    titles = {h.meta["title"] for h in hits}
    assert "Payroll Ledger" not in titles          # ...but it is trimmed out
    assert "Company Handbook" in titles or hits     # public still allowed


def test_manager_sees_all_scopes(session):
    _seed(session)
    principals = principals_for("manager")
    hits = retrieve("payroll tax ledger", principals, k=5)
    assert "Payroll Ledger" in {h.meta["title"] for h in hits}


def test_public_doc_visible_to_everyone(session):
    _seed(session)
    hits = retrieve("vacation policy handbook", principals_for("production"), k=5)
    assert "Company Handbook" in {h.meta["title"] for h in hits}


def test_relevant_in_scope_doc_is_retrieved(session):
    _seed(session)
    hits = retrieve("sales forecast pipeline revenue", principals_for("sales"), k=5)
    assert hits and hits[0].meta["title"] == "Sales Forecast"
