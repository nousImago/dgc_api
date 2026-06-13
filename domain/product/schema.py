from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RatingDimensionIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    data_type: str = Field(pattern="^(int|str)$")
    position: int = 0


class RatingDimensionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    data_type: str
    position: int


class ProductCreate(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="base", pattern="^(base|rider)$")
    dimensions: list[RatingDimensionIn] = Field(default_factory=list)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    kind: str
    active: bool
    dimensions: list[RatingDimensionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
