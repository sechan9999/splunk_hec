import pytest
from fastapi import HTTPException

from app.domain.models import Employee
from app.experience.workspace import assemble_workspace, get_layout, save_layout
from app.security.auth import issue_token, resolve_identity


def _employee(session, role):
    emp = Employee(name=f"{role}-user", role=role)
    session.add(emp)
    session.commit()
    token = issue_token(session, emp)
    return emp, token


# --- auth -------------------------------------------------------------------
def test_token_resolves_to_identity_with_role(session):
    emp, token = _employee(session, "manager")
    identity = resolve_identity(session, token)
    assert identity.employee_id == emp.id
    assert identity.role == "manager"
    assert "grp:all" in identity.principals


def test_invalid_token_rejected(session):
    with pytest.raises(HTTPException) as exc:
        resolve_identity(session, "nope")
    assert exc.value.status_code == 401


# --- workspace assembly -----------------------------------------------------
def test_manager_workspace_has_full_preset(session):
    emp, token = _employee(session, "manager")
    ws = assemble_workspace(session, resolve_identity(session, token))
    ids = {w["id"] for w in ws["widgets"]}
    assert {"pipeline", "performance", "inventory", "accounting_health", "insights"} <= ids


def test_sales_cannot_see_performance_widget(session):
    emp, token = _employee(session, "sales")
    ws = assemble_workspace(session, resolve_identity(session, token))
    ids = {w["id"] for w in ws["widgets"]}
    assert "performance" not in ids
    assert "pipeline" in ids  # sales preset


# --- personalization + RBAC defense ----------------------------------------
def test_saved_layout_overrides_preset(session):
    emp, token = _employee(session, "manager")
    identity = resolve_identity(session, token)
    save_layout(session, identity, ["insights", "pipeline", "bogus_widget"])
    assert get_layout(session, identity) == ["insights", "pipeline"]  # bogus filtered


def test_saved_layout_still_rbac_filtered(session):
    emp, token = _employee(session, "sales")
    identity = resolve_identity(session, token)
    save_layout(session, identity, ["performance", "pipeline"])  # sales tries to add performance
    assert get_layout(session, identity) == ["pipeline"]  # performance stripped by RBAC
