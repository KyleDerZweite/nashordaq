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
    PlayingIncomeEntry,
    PoroSpawn,
    PoroSpawnStatus,
    TrackedPlayer,
    User,
    UserWealthSnapshot,
    UserWealthSnapshotSource,
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
    rescue_loan_amount: float
    rescue_loan_uses_remaining: int
    rescue_loan_interest_rate: float
    rescue_loan_upfront_interest_amount: float
    rescue_net_worth_threshold: float
    rescue_loan_available: bool
    rescue_loan_block_reason: str | None
    next_interest_accrual_at: datetime | None
    next_interest_amount: float
    interest_rate_per_interval: float


@dataclass(slots=True)
class PlayingIncomeSummary:
    projected_next_win_income: float
    projected_next_loss_income: float
    playing_income_last_24h: float
    playing_income_lifetime_total: float
    recent_entries: list[PlayingIncomeEntry]


@dataclass(slots=True)
class BalanceInsightsSummary:
    snapshot: AccountSnapshot
    playing_income: PlayingIncomeSummary
    history: list[UserWealthSnapshot]


def round_currency(value: float) -> float:
    return round(value + 1e-9, 2)


def start_of_utc_day(value: datetime) -> datetime:
    normalized_value = normalize_datetime(value) or datetime.now(UTC)
    return normalized_value.replace(hour=0, minute=0, second=0, microsecond=0)


def get_playing_income_daily_multiplier(match_number_for_day: int) -> float:
    match_number = max(1, match_number_for_day)
    if match_number <= settings.playing_income_boosted_games_per_day:
        return 1.0
    return settings.playing_income_grind_daily_multiplier


def get_playing_income_outcome_multiplier(
    won_match: bool, match_number_for_day: int
) -> float:
    del match_number_for_day
    if won_match:
        return 1.0
    return settings.playing_income_loss_multiplier


def get_playing_income_base_payout(won_match: bool) -> float:
    return (
        settings.playing_income_win_base_payout
        if won_match
        else settings.playing_income_loss_base_payout
    )


def calculate_playing_income_amount(
    share_price: float,
    outcome_multiplier: float,
    *,
    base_payout: float,
    daily_multiplier: float,
) -> float:
    variable = (
        share_price
        * settings.playing_income_base_rate
        * outcome_multiplier
        * daily_multiplier
    )
    return round_currency(base_payout + variable)


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


def get_bank_interest_rate(base_amount: float) -> float:
    return settings.bank_rescue_interest_rate_per_interval


def calculate_bank_interest(base_amount: float) -> float:
    return round_currency(base_amount * get_bank_interest_rate(base_amount))


def calculate_borrow_interest(
    borrow_amount: float,
    projected_outstanding_debt: float,
) -> float:
    normalized_borrow_amount = max(0.0, round_currency(borrow_amount))
    return round_currency(
        normalized_borrow_amount * get_bank_interest_rate(projected_outstanding_debt)
    )


def get_rescue_loan_block_reason(
    *,
    debt_adjusted_net_worth: float,
    outstanding_debt: float,
    rescue_loan_uses_remaining: int,
) -> str | None:
    if outstanding_debt > 0:
        return "Rescue loan unavailable while debt is outstanding"
    if rescue_loan_uses_remaining <= 0:
        return "Rescue loan already used. Ask an admin to restore it"
    if debt_adjusted_net_worth > settings.bank_rescue_net_worth_threshold:
        return (
            "Rescue loan unlocks once net worth falls to "
            f"{settings.bank_rescue_net_worth_threshold:.0f} P or below"
        )
    return None


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
        next_accrual_at = (
            normalize_datetime(as_of) or datetime.now(UTC)
        ) + interest_interval()

    pending_intervals = _pending_interest_intervals(next_accrual_at, as_of)
    preview_interest = accrued_interest
    preview_next = next_accrual_at

    for _ in range(pending_intervals):
        preview_outstanding = round_currency(principal + preview_interest)
        preview_interest = round_currency(
            preview_interest + calculate_bank_interest(preview_outstanding)
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
    rescue_loan_uses_remaining = max(0, int(user.rescue_loan_uses_remaining or 0))
    rescue_loan_block_reason = get_rescue_loan_block_reason(
        debt_adjusted_net_worth=debt_adjusted_net_worth,
        outstanding_debt=debt_preview.outstanding_debt,
        rescue_loan_uses_remaining=rescue_loan_uses_remaining,
    )
    rescue_loan_available = rescue_loan_block_reason is None
    rescue_loan_amount = round_currency(settings.bank_rescue_loan_amount)
    rescue_loan_interest_rate = settings.bank_rescue_interest_rate_per_interval
    rescue_loan_upfront_interest_amount = calculate_borrow_interest(
        rescue_loan_amount,
        rescue_loan_amount,
    )
    interest_rate_per_interval = get_bank_interest_rate(debt_preview.outstanding_debt)
    next_interest_amount = (
        calculate_bank_interest(debt_preview.outstanding_debt)
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
        rescue_loan_amount=rescue_loan_amount,
        rescue_loan_uses_remaining=rescue_loan_uses_remaining,
        rescue_loan_interest_rate=rescue_loan_interest_rate,
        rescue_loan_upfront_interest_amount=rescue_loan_upfront_interest_amount,
        rescue_net_worth_threshold=round_currency(
            settings.bank_rescue_net_worth_threshold
        ),
        rescue_loan_available=rescue_loan_available,
        rescue_loan_block_reason=rescue_loan_block_reason,
        next_interest_accrual_at=debt_preview.next_accrual_at,
        next_interest_amount=next_interest_amount,
        interest_rate_per_interval=interest_rate_per_interval,
    )


async def build_playing_income_summary(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> PlayingIncomeSummary:
    now = normalize_datetime(as_of) or datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=24)

    lifetime_total_result = await session.scalar(
        select(func.coalesce(func.sum(PlayingIncomeEntry.amount), 0.0)).where(
            PlayingIncomeEntry.user_id == user.id
        )
    )
    recent_total_result = await session.scalar(
        select(func.coalesce(func.sum(PlayingIncomeEntry.amount), 0.0)).where(
            PlayingIncomeEntry.user_id == user.id,
            PlayingIncomeEntry.match_completed_at >= recent_cutoff,
        )
    )
    recent_entries_result = await session.execute(
        select(PlayingIncomeEntry)
        .where(PlayingIncomeEntry.user_id == user.id)
        .order_by(
            PlayingIncomeEntry.match_completed_at.desc(),
            PlayingIncomeEntry.id.desc(),
        )
        .limit(8)
    )
    recent_entries = list(recent_entries_result.scalars().all())

    linked_player = None
    if user.linked_player_id is not None:
        linked_player = await session.get(TrackedPlayer, user.linked_player_id)

    share_price = linked_player.current_price if linked_player is not None else 0.0
    today_start = start_of_utc_day(now)
    tomorrow_start = today_start + timedelta(days=1)
    rewarded_matches_today_result = await session.scalar(
        select(func.count(PlayingIncomeEntry.id)).where(
            PlayingIncomeEntry.user_id == user.id,
            PlayingIncomeEntry.match_completed_at >= today_start,
            PlayingIncomeEntry.match_completed_at < tomorrow_start,
        )
    )
    next_match_number = int(rewarded_matches_today_result or 0) + 1
    next_win_daily_multiplier = get_playing_income_daily_multiplier(next_match_number)
    next_loss_daily_multiplier = get_playing_income_daily_multiplier(next_match_number)

    return PlayingIncomeSummary(
        projected_next_win_income=calculate_playing_income_amount(
            share_price,
            get_playing_income_outcome_multiplier(True, next_match_number),
            base_payout=get_playing_income_base_payout(True),
            daily_multiplier=next_win_daily_multiplier,
        ),
        projected_next_loss_income=calculate_playing_income_amount(
            share_price,
            get_playing_income_outcome_multiplier(False, next_match_number),
            base_payout=get_playing_income_base_payout(False),
            daily_multiplier=next_loss_daily_multiplier,
        ),
        playing_income_last_24h=round_currency(float(recent_total_result or 0.0)),
        playing_income_lifetime_total=round_currency(
            float(lifetime_total_result or 0.0)
        ),
        recent_entries=recent_entries,
    )


async def build_poro_rewards_summary(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> tuple[float, float]:
    now = normalize_datetime(as_of) or datetime.now(UTC)
    recent_cutoff = now - timedelta(hours=24)

    lifetime_total_result = await session.scalar(
        select(func.coalesce(func.sum(PoroSpawn.reward_amount), 0.0)).where(
            PoroSpawn.user_id == user.id,
            PoroSpawn.status == PoroSpawnStatus.CLAIMED,
            PoroSpawn.claimed_at.is_not(None),
        )
    )
    recent_total_result = await session.scalar(
        select(func.coalesce(func.sum(PoroSpawn.reward_amount), 0.0)).where(
            PoroSpawn.user_id == user.id,
            PoroSpawn.status == PoroSpawnStatus.CLAIMED,
            PoroSpawn.claimed_at.is_not(None),
            PoroSpawn.claimed_at >= recent_cutoff,
        )
    )

    return (
        round_currency(float(recent_total_result or 0.0)),
        round_currency(float(lifetime_total_result or 0.0)),
    )


async def record_user_wealth_snapshot(
    session: AsyncSession,
    user: User,
    *,
    source: UserWealthSnapshotSource,
    as_of: datetime | None = None,
) -> UserWealthSnapshot:
    snapshot = await build_account_snapshot(session, user, as_of=as_of)
    entry = UserWealthSnapshot(
        user_id=user.id,
        source=source,
        cash_balance=snapshot.cash_balance,
        holdings_value=snapshot.holdings_value,
        active_gamba_value=snapshot.active_gamba_value,
        debt_outstanding=snapshot.debt_outstanding,
        net_worth=snapshot.debt_adjusted_net_worth,
        recorded_at=normalize_datetime(as_of) or datetime.now(UTC),
    )
    session.add(entry)
    return entry


async def build_balance_insights_summary(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
    history_limit: int = 16,
) -> BalanceInsightsSummary:
    snapshot = await build_account_snapshot(session, user, as_of=as_of)
    playing_income = await build_playing_income_summary(session, user, as_of=as_of)
    (
        poro_rewards_last_24h,
        poro_rewards_lifetime_total,
    ) = await build_poro_rewards_summary(session, user, as_of=as_of)
    history_result = await session.execute(
        select(UserWealthSnapshot)
        .where(UserWealthSnapshot.user_id == user.id)
        .order_by(UserWealthSnapshot.recorded_at.desc(), UserWealthSnapshot.id.desc())
        .limit(history_limit)
    )
    history = list(reversed(history_result.scalars().all()))

    return BalanceInsightsSummary(
        snapshot=snapshot,
        playing_income=PlayingIncomeSummary(
            projected_next_win_income=playing_income.projected_next_win_income,
            projected_next_loss_income=playing_income.projected_next_loss_income,
            playing_income_last_24h=round_currency(
                playing_income.playing_income_last_24h + poro_rewards_last_24h
            ),
            playing_income_lifetime_total=round_currency(
                playing_income.playing_income_lifetime_total
                + poro_rewards_lifetime_total
            ),
            recent_entries=playing_income.recent_entries,
        ),
        history=history,
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
        interest_amount = calculate_bank_interest(outstanding_before)
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
    user.rescue_loan_uses_remaining = max(0, user.rescue_loan_uses_remaining - 1)
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


def apply_borrow_interest(
    user: User, amount: float, *, at: datetime
) -> BankLedgerEntry:
    interest_amount = calculate_borrow_interest(
        amount,
        current_outstanding_debt(user),
    )
    user.debt_accrued_interest = round_currency(
        user.debt_accrued_interest + interest_amount
    )

    return BankLedgerEntry(
        user_id=user.id,
        entry_type=BankLedgerEntryType.INTEREST,
        amount=interest_amount,
        principal_change=0.0,
        interest_change=interest_amount,
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


def restore_rescue_loan_use(user: User) -> None:
    user.rescue_loan_uses_remaining = 1
