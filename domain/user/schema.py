from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RoleRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str


class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    phone: str | None = None


class UserCreate(UserBase):
    password: str = Field(min_length=8)
    role_ids: list[int] = Field(default_factory=list)


class UserPasswordUpdate(BaseModel):
    password: str = Field(min_length=8)


class UserUpdate(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    active: bool | None = None
    role_ids: list[int] | None = None


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    active: bool
    # Override base EmailStr with plain str so legacy/reserved-TLD addresses
    # don't 500 the search endpoint.
    email: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    roles: list[RoleRef] = Field(default_factory=list)
    # Flat list of permission codes granted by the user's roles. Populated
    # by auth_service on login; empty by default when loading from ORM.
    permissions: list[str] = Field(default_factory=list)
