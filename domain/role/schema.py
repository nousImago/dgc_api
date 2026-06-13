from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PermissionRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str


class RoleBase(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    active: bool = True


class RoleCreate(RoleBase):
    permission_ids: list[int] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    active: bool | None = None
    permission_ids: list[int] | None = None


class RoleOut(RoleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
    permissions: list[PermissionRef] = Field(default_factory=list)
