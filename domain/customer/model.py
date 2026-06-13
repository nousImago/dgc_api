from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from domain.policy.model import Policy


class Customer(IdMixin, TimestampMixin, Base):
    """The insured person. Holds the rating-relevant facts: sex and date of
    birth. Age is never stored — it is derived from `date_of_birth` at a
    policy's effective date (see services.rating.age_last_birthday)."""

    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("sex IN ('M','F')", name="sex_valid"),)

    external_ref: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sex: Mapped[str] = mapped_column(String(1), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)

    policies: Mapped[list["Policy"]] = relationship(
        back_populates="customer",
        lazy="selectin",
    )
