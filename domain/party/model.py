from datetime import date

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from domain.base import Base, IdMixin, TimestampMixin


class Party(IdMixin, TimestampMixin, Base):
    """The master identity record for any person or organization the insurer
    deals with — deduplicated, one row per real-world entity. A party relates to
    policies through `policy_roles` (owner / insured / beneficiary) and can hold
    different roles on different policies. For persons, `sex` + `date_of_birth`
    are the rating attributes read when the party is the *insured*."""

    __tablename__ = "parties"
    __table_args__ = (
        CheckConstraint("sex IN ('M','F')", name="sex_valid"),
        CheckConstraint("party_type IN ('person','org')", name="party_type_valid"),
    )

    external_ref: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    party_type: Mapped[str] = mapped_column(String(8), nullable=False, default="person")
    sex: Mapped[str] = mapped_column(String(1), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
