"""Workspace role and permission helpers."""
from app.models.workspace_member import WorkspaceMember


def can_manage_secrets(role: str) -> bool:
    return role in ("owner", "admin")


def can_manage_billing_members_teams(role: str) -> bool:
    return role in ("owner", "admin")


def can_edit_teams(role: str) -> bool:
    return role in ("owner", "admin", "member")


def can_run_teams(role: str) -> bool:
    return role in ("owner", "admin", "member")


def can_view_runs(role: str) -> bool:
    return role in ("owner", "admin", "member")


def can_view_outputs_only(role: str) -> bool:
    return role == "viewer"
