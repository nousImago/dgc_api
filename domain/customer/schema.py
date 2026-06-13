from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    external_ref: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    sex: str = Field(pattern="^[MF]$")
    date_of_birth: date


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime
