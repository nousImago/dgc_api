from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from domain.base import Base, IdMixin

if TYPE_CHECKING:
    from domain.role.model import Role


class Permission(IdMixin, Base):
    """Seeded RBAC permission. One row per code-enforced action.

    Examples of codes:
        job_auto.create
        job_auto.approve_finance
        invoice.void
        leave.approve
    """

    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    roles: Mapped[list["Role"]] = relationship(
        secondary="role_permission",
        back_populates="permissions",
        lazy="selectin",
    )
