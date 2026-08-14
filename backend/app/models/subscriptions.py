import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class Plan(Base, UUIDPKMixin, TimestampMixin):
    """A billable tier a tenant organization subscribes to. Reference data --
    seeded once via migration, not created through the API."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)  # starter|growth|enterprise
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=False)
    # None means unlimited -- Enterprise has no cap, so a NULL/None check
    # (not a huge integer) is how "unlimited" is represented everywhere
    # this is read (see OrganizationService.create_branch, AuthService.create_user).
    max_branches: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    razorpay_plan_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subscription(Base, UUIDPKMixin, TimestampMixin):
    """One row per tenant -- the org's current billing relationship. Status
    transitions: trialing -> active (first successful charge) -> past_due
    (renewal failed) -> canceled. `get_current_user` (core/deps.py) reads
    this to decide whether to let a request through at all; OrganizationService
    and AuthService read the joined Plan to enforce branch/user caps."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_subscription_org"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    plan_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="trialing")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    plan: Mapped["Plan"] = relationship()


class PasswordResetToken(Base, UUIDPKMixin):
    """Single-use, short-lived token for the forgot-password flow. Stored
    (rather than a stateless JWT) so a token can be invalidated the moment
    it's used -- a reused reset link/email is a real attack scenario a
    stateless JWT can't defend against without its own revocation list."""

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailVerificationToken(Base, UUIDPKMixin):
    """Single-use token proving ownership of a signup email address. Mirrors
    PasswordResetToken: stored so it can be invalidated on use, never a
    stateless JWT."""

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
