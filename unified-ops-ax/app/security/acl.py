"""Security Trimming — retrieval-time access control mirroring the source
system's ACLs. A document/chunk is visible only if its ACL intersects the
caller's principals. Empty ACL == public."""
from __future__ import annotations


def can_access(resource_acl: list[str] | None, user_principals: set[str] | list[str]) -> bool:
    if not resource_acl:  # public
        return True
    principals = set(user_principals)
    return bool(principals.intersection(resource_acl))


def trim(items: list, acl_getter, user_principals: set[str] | list[str]) -> list:
    principals = set(user_principals)
    return [it for it in items if can_access(acl_getter(it), principals)]
