"""Workspace and member schemas."""
from datetime import datetime

from pydantic import BaseModel, EmailStr


class WorkspaceBase(BaseModel):
    name: str
    slug: str | None = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None


class WorkspaceResponse(WorkspaceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceListResponse(BaseModel):
    id: int
    name: str
    slug: str | None
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberResponse(BaseModel):
    user_id: int
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberInvite(BaseModel):
    email: EmailStr
    role: str  # admin, member, viewer


class MemberUpdateRole(BaseModel):
    role: str  # admin, member, viewer


class SecretCreate(BaseModel):
    key_name: str
    value: str
    chain_id: int | None = None


class SecretListItem(BaseModel):
    key_name: str
    chain_id: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Workspace Personalities ----

class PersonalityCreate(BaseModel):
    name: str
    content: str = ""
    chain_id: int | None = None


class PersonalityUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    source: str | None = None


class PersonalityListItem(BaseModel):
    id: int
    name: str
    chain_id: int | None
    source: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PersonalityResponse(BaseModel):
    id: int
    workspace_id: int
    chain_id: int | None
    name: str
    content: str
    source: str
    source_run_id: int | None
    source_node_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
