import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import (
    BankLedgerEntry,
    BankLedgerEntryType,
    GambaPosition,
    GambaStatus,
    Holding,
    TrackedPlayer,
    User,
)


@dataclass(slots=True)
class DebtPreview:
    principal: float
    accrued_interest: float
    outstanding_debt: float
    next_accrual_at: datetime | None
    pending_intervals: int


@dataclass(slots=True)
class AccountSnapshot:
    cash_balance: float
    holdings_value: float
    active_gamba_value: float
    debt_principal: float
    debt_accrued_interest: float
    debt_outstanding: float
    debt_adjusted_net_worth: float
    credit_limit: float
    available_credit: float
    next_interest_accrual_at: datetime | None
    next_interest_amount: float


def round_currency(value: float) -> float:
    return round(value + 1e-9, 2)


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def interest_interval() -> timedelta:
    return timedelta(hours=settings.bank_interest_interval_hours)


def current_outstanding_debt(user: User) -> float:
    return round_currency(user.debt_principal + user.debt_accrued_interest)


def floor_to_increment(value: float, increment: float) -> float:
    if value <= 0 or increment <= 0:
        return 0.0
    return round_currency(math.floor(value / increment) * increment)


def calculate_credit_limit(debt_adjusted_net_worth: float) -> float:
    raw_limit = (
        debt_adjusted_net_worth * settings.bank_max_borrow_net_worth_ratio
        + settings.bank_base_credit_limit
    )
    credit_limit = floor_to_increment(
        max(0.0, raw_limit),
        settings.bank_credit_limit_rounding_increment,
    )
    return round_currency(min(settings.bank_max_borrow_absolute, credit_limit))


def _pending_interest_intervals(
    next_accrual_at: datetime | None,
    as_of: datetime,
) -> int:
    normalized_next = normalize_datetime(next_accrual_at)
    normalized_as_of = normalize_datetime(as_of)
    if normalized_next is None or normalized_as_of is None:
        return 0
    if normalized_as_of < normalized_next:
        return 0

    interval_seconds = interest_interval().total_seconds()
    elapsed_seconds = (normalized_as_of - normalized_next).total_seconds()
    return int(elapsed_seconds // interval_seconds) + 1


def preview_debt(user: User, as_of: datetime) -> DebtPreview:
    principal = round_currency(user.debt_principal)
    accrued_interest = round_currency(user.debt_accrued_interest)
    next_accrual_at = normalize_datetime(user.debt_next_accrual_at)
    outstanding_debt = round_currency(principal + accrued_interest)

    if outstanding_debt <= 0:
        return DebtPreview(
            principal=0.0,
            accrued_interest=0.0,
            outstanding_debt=0.0,
            next_accrual_at=None,
            pending_intervals=0,
        )

    if next_accrual_at is None:
        next_accrual_at = normalize_datetime(as_of) + interest_interval()

    pending_intervals = _pending_interest_intervals(next_accrual_at, as_of)
    preview_interest = accrued_interest
    preview_next = next_accrual_at

    for _ in range(pending_intervals):
        preview_outstanding = round_currency(principal + preview_interest)
        preview_interest = round_currency(
            preview_interest
            + round_currency(
                preview_outstanding * settings.bank_interest_rate_per_interval
            )
        )
        preview_next = preview_next + interest_interval()

    return DebtPreview(
        principal=principal,
        accrued_interest=preview_interest,
        outstanding_debt=round_currency(principal + preview_interest),
        next_accrual_at=preview_next,
        pending_intervals=pending_intervals,
    )


def _clear_debt_schedule_if_empty(user: User) -> None:
    if current_outstanding_debt(user) > 0:
        return

    user.debt_principal = 0.0
    user.debt_accrued_interest = 0.0
    user.debt_last_accrued_at = None
    user.debt_next_accrual_at = None


async def get_holdings_value(session: AsyncSession, user_id: int) -> float:
    result = await session.scalar(
        select(
            func.coalesce(func.sum(Holding.quantity * TrackedPlayer.current_price), 0.0)
        )
        .select_from(Holding)
        .join(TrackedPlayer, TrackedPlayer.id == Holding.player_id)
        .where(Holding.user_id == user_id, Holding.quantity > 0)
    )
    return round_currency(float(result or 0.0))


async def get_active_gamba_value(session: AsyncSession, user_id: int) -> float:
    result = await session.scalar(
        select(
            func.coalesce(
                func.sum(GambaPosition.quantity * TrackedPlayer.current_price),
                0.0,
            )
        )
        .select_from(GambaPosition)
        .join(TrackedPlayer, TrackedPlayer.id == GambaPosition.player_id)
        .where(
            GambaPosition.user_id == user_id,
            GambaPosition.status == GambaStatus.ACTIVE,
        )
    )
    return round_currency(float(result or 0.0))


async def build_account_snapshot(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> AccountSnapshot:
    now = normalize_datetime(as_of) or datetime.now(UTC)
    holdings_value = await get_holdings_value(session, user.id)
    active_gamba_value = await get_active_gamba_value(session, user.id)
    debt_preview = preview_debt(user, now)
    debt_adjusted_net_worth = round_currency(
        user.balance
        + holdings_value
        + active_gamba_value
        - debt_preview.outstanding_debt
    )
    credit_limit = calculate_credit_limit(debt_adjusted_net_worth)
    available_credit = round_currency(
        max(0.0, credit_limit - debt_preview.outstanding_debt)
    )
    next_interest_amount = (
        round_currency(
            debt_preview.outstanding_debt * settings.bank_interest_rate_per_interval
        )
        if debt_preview.outstanding_debt > 0
        else 0.0
    )

    return AccountSnapshot(
        cash_balance=round_currency(user.balance),
        holdings_value=holdings_value,
        active_gamba_value=active_gamba_value,
        debt_principal=debt_preview.principal,
        debt_accrued_interest=debt_preview.accrued_interest,
        debt_outstanding=debt_preview.outstanding_debt,
        debt_adjusted_net_worth=debt_adjusted_net_worth,
        credit_limit=credit_limit,
        available_credit=available_credit,
        next_interest_accrual_at=debt_preview.next_accrual_at,
        next_interest_amount=next_interest_amount,
    )


async def apply_due_interest(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime,
) -> int:
    now = normalize_datetime(as_of) or datetime.now(UTC)
    if current_outstanding_debt(user) <= 0:
        _clear_debt_schedule_if_empty(user)
        return 0

    if user.debt_next_accrual_at is None:
        user.debt_last_accrued_at = now
        user.debt_next_accrual_at = now + interest_interval()
        return 0

    applied_intervals = 0
    next_accrual_at = normalize_datetime(user.debt_next_accrual_at)
    while next_accrual_at is not None and next_accrual_at <= now:
        outstanding_before = current_outstanding_debt(user)
        interest_amount = round_currency(
            outstanding_before * settings.bank_interest_rate_per_interval
        )
        user.debt_accrued_interest = round_currency(
            user.debt_accrued_interest + interest_amount
        )
        user.debt_last_accrued_at = next_accrual_at
        next_accrual_at = next_accrual_at + interest_interval()
        user.debt_next_accrual_at = next_accrual_at
        session.add(
            BankLedgerEntry(
                user_id=user.id,
                entry_type=BankLedgerEntryType.INTEREST,
                amount=interest_amount,
                principal_change=0.0,
                interest_change=interest_amount,
                outstanding_debt=current_outstanding_debt(user),
                created_at=user.debt_last_accrued_at,
            )
        )
        applied_intervals += 1

    _clear_debt_schedule_if_empty(user)
    return applied_intervals


def initialize_debt_schedule(user: User, *, at: datetime) -> None:
    now = normalize_datetime(at) or datetime.now(UTC)
    user.debt_last_accrued_at = now
    user.debt_next_accrual_at = now + interest_interval()


def apply_borrow(user: User, amount: float, *, at: datetime) -> BankLedgerEntry:
    normalized_amount = round_currency(amount)
    user.balance = round_currency(user.balance + normalized_amount)
    user.debt_principal = round_currency(user.debt_principal + normalized_amount)
    if current_outstanding_debt(user) > 0 and user.debt_next_accrual_at is None:
        initialize_debt_schedule(user, at=at)

    return BankLedgerEntry(
        user_id=user.id,
        entry_type=BankLedgerEntryType.BORROW,
        amount=normalized_amount,
        principal_change=normalized_amount,
        interest_change=0.0,
        outstanding_debt=current_outstanding_debt(user),
        created_at=normalize_datetime(at),
    )


def apply_repayment(user: User, amount: float, *, at: datetime) -> BankLedgerEntry:
    outstanding_before = current_outstanding_debt(user)
    repayment_amount = round_currency(min(amount, outstanding_before))
    interest_paid = round_currency(min(repayment_amount, user.debt_accrued_interest))
    remaining = round_currency(repayment_amount - interest_paid)
    principal_paid = round_currency(min(remaining, user.debt_principal))

    user.balance = round_currency(user.balance - repayment_amount)
    user.debt_accrued_interest = round_currency(
        user.debt_accrued_interest - interest_paid
    )
    user.debt_principal = round_currency(user.debt_principal - principal_paid)
    _clear_debt_schedule_if_empty(user)

    if current_outstanding_debt(user) > 0 and user.debt_next_accrual_at is None:
        initialize_debt_schedule(user, at=at)

    return BankLedgerEntry(
        user_id=user.id,
        entry_type=BankLedgerEntryType.REPAYMENT,
        amount=repayment_amount,
        principal_change=-principal_paid,
        interest_change=-interest_paid,
        outstanding_debt=current_outstanding_debt(user),
        created_at=normalize_datetime(at),
    )
