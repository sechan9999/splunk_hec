from app.domain.models import Customer, Employee
from app.domain.services import open_as_ticket
from app.security.auth import Identity
from app.security.pii import PiiCipher
from app.security.rls import can_view_customer, scope_customers, scope_open_tickets


def _id(emp: Employee, role: str) -> Identity:
    return Identity(emp.id, emp.name, role, set())


# --- PII field encryption ---------------------------------------------------
def test_pii_roundtrip_with_key():
    c = PiiCipher("secret")
    ct = c.encrypt("alice@example.com")
    assert ct.startswith("enc:v1:")
    assert ct != "alice@example.com"
    assert c.decrypt(ct) == "alice@example.com"


def test_pii_noop_without_key():
    c = PiiCipher(None)
    assert c.encrypt("x@e.com") == "x@e.com"
    assert c.decrypt("x@e.com") == "x@e.com"


def test_pii_decrypt_safe_on_plaintext_and_nondeterministic():
    c = PiiCipher("k")
    assert c.decrypt("legacy-plain") == "legacy-plain"       # no prefix -> returned as-is
    assert c.encrypt("same") != c.encrypt("same")            # random nonce
    assert c.decrypt(c.encrypt("same")) == "same"


def test_customer_pii_encrypted_at_rest(session):
    c = PiiCipher("k")
    cust = Customer(name="X", email=c.encrypt("x@e.com"), phone=c.encrypt("010-1"))
    session.add(cust)
    session.commit()
    stored = session.get(Customer, cust.id)
    assert stored.email.startswith("enc:v1:")                # ciphertext in DB
    assert c.decrypt(stored.email) == "x@e.com"


# --- Row-Level Security -----------------------------------------------------
def test_sales_sees_only_own_customers(session):
    s1 = Employee(name="S1", role="sales")
    s2 = Employee(name="S2", role="sales")
    session.add_all([s1, s2])
    session.commit()
    a = Customer(name="A", owner_employee_id=s1.id)
    b = Customer(name="B", owner_employee_id=s2.id)
    session.add_all([a, b])
    session.commit()

    id1 = _id(s1, "sales")
    assert {c.name for c in scope_customers(session, id1)} == {"A"}
    assert can_view_customer(session, id1, a.id) is True
    assert can_view_customer(session, id1, b.id) is False


def test_manager_sees_all_customers(session):
    mgr = Employee(name="M", role="manager")
    session.add(mgr)
    session.commit()
    session.add_all([Customer(name="A"), Customer(name="B")])
    session.commit()
    idm = _id(mgr, "manager")
    assert len(scope_customers(session, idm)) == 2
    any_id = session.query(Customer).first().id
    assert can_view_customer(session, idm, any_id) is True


def test_as_sees_assigned_and_unassigned_tickets(session):
    as1 = Employee(name="AS1", role="as")
    as2 = Employee(name="AS2", role="as")
    cust = Customer(name="C")
    session.add_all([as1, as2, cust])
    session.commit()
    mine = open_as_ticket(session, customer_id=cust.id, summary="mine")
    mine.assignee_id = as1.id
    theirs = open_as_ticket(session, customer_id=cust.id, summary="theirs")
    theirs.assignee_id = as2.id
    open_as_ticket(session, customer_id=cust.id, summary="pool")  # unassigned
    session.commit()

    summaries = {t.summary for t in scope_open_tickets(session, _id(as1, "as"))}
    assert "mine" in summaries and "pool" in summaries
    assert "theirs" not in summaries


def test_as_cannot_view_unrelated_customer(session):
    as1 = Employee(name="AS1", role="as")
    other = Customer(name="Other")
    session.add_all([as1, other])
    session.commit()
    assert can_view_customer(session, _id(as1, "as"), other.id) is False
