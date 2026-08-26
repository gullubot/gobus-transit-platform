"""
Transit Platform — User & Operator Profile Models.

BUILD 1: User accounts and operator profiles.
No authentication logic — only schema.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.enums import UserRole, VerificationStatus


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole", create_constraint=False),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    organization = relationship("Organization", back_populates="users", lazy="select")
    operator_profile = relationship(
        "OperatorProfile", back_populates="user", uselist=False, lazy="select"
    )
    trip_assignments = relationship("TripAssignment", back_populates="user", lazy="select")

    __table_args__ = (
        # Composite key for org-scoped composite FKs
        UniqueConstraint("id", "organization_id", name="uq_users_id_org"),
    )

    def __repr__(self) -> str:
        return f"<User {self.name!r} role={self.role.value}>"


class OperatorProfile(Base):
    """
    Operator profile — linked 1:1 to a User.

    Organization ownership is inherited from user.organization_id.
    employee_code uniqueness within organization is enforced at
    the application level since the org comes through the user relation.
    """

    __tablename__ = "operator_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    operator_type: Mapped[str] = mapped_column(String(20), nullable=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verificationstatus", create_constraint=False),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ────────────────────────────────────────────────
    user = relationship("User", back_populates="operator_profile", lazy="select")

    def __repr__(self) -> str:
        return f"<OperatorProfile {self.employee_code!r} type={self.operator_type}>"
