from pydantic import BaseModel, ConfigDict, Field


class PermissionBase(BaseModel):
    code: str = Field(min_length=3, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    resource: str = Field(min_length=1, max_length=64)
    action: str = Field(min_length=1, max_length=64)


class PermissionOut(PermissionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
