"""Role -> default principals. Principals drive both API authorization and
document security trimming, so RBAC and ACL share one vocabulary."""
from __future__ import annotations

ROLE_PRINCIPALS: dict[str, list[str]] = {
    "sales": ["grp:all", "grp:sales"],
    "production": ["grp:all", "grp:production"],
    "as": ["grp:all", "grp:as"],
    "accounting": ["grp:all", "grp:accounting"],
    "manager": ["grp:all", "grp:sales", "grp:production", "grp:as", "grp:accounting", "grp:manager"],
}


def principals_for(role: str, employee_id: str | None = None, extra: list[str] | None = None) -> set[str]:
    principals = set(ROLE_PRINCIPALS.get(role, ["grp:all"]))
    if employee_id:
        principals.add(f"usr:{employee_id}")
    if extra:
        principals.update(extra)
    return principals
