from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentOnboardedUser
from app.banking import (
    apply_borrow,
    apply_borrow_interest,
    apply_due_interest,
    apply_repayment,
    build_account_snapshot,
    build_playing_income_summary,
    current_outstanding_debt,
    record_user_wealth_snapshot,
    round_currency,
)
from app.config import settings
from app.database import get_session
from app.models import BankLedgerEntry, User, UserWealthSnapshotSource
from app.schemas import (
    BankActionRequest,
    BankLedgerEntryResponse,
    BankSummaryResponse,
    PlayingIncomeEntryResponse,
)

router = APIRouter(tags=["bank"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _build_bank_summary(
    session: AsyncSession,
    user: User,
    *,
    as_of: datetime | None = None,
) -> BankSummaryResponse:
    snapshot = await build_account_snapshot(session, user, as_of=as_of)
    playing_income = await build_playing_income_summary(session, user, as_of=as_of)
    entries_result = await session.execute(
        select(BankLedgerEntry)
        .where(BankLedgerEntry.user_id == user.id)
        .order_by(BankLedgerEntry.created_at.desc(), BankLedgerEntry.id.desc())
        .limit(8)
    )
    entries = entries_result.scalars().all()

    return BankSummaryResponse(
        cash_balance=snapshot.cash_balance,
        holdings_value=snapshot.holdings_value,
        active_gamba_value=snapshot.active_gamba_value,
        debt_principal=snapshot.debt_principal,
        debt_accrued_interest=snapshot.debt_accrued_interest,
        debt_outstanding=snapshot.debt_outstanding,
        debt_adjusted_net_worth=snapshot.debt_adjusted_net_worth,
        credit_limit=snapshot.credit_limit,
        available_credit=snapshot.available_credit,
        next_interest_accrual_at=snapshot.next_interest_accrual_at,
        next_interest_amount=snapshot.next_interest_amount,
        interest_rate_per_interval=snapshot.interest_rate_per_interval,
        interest_interval_hours=settings.bank_interest_interval_hours,
        projected_next_win_income=playing_income.projected_next_win_income,
        projected_next_loss_income=playing_income.projected_next_loss_income,
        playing_income_last_24h=playing_income.playing_income_last_24h,
        playing_income_lifetime_total=playing_income.playing_income_lifetime_total,
        recent_entries=[
            BankLedgerEntryResponse(
                id=entry.id,
                entry_type=entry.entry_type,
                amount=entry.amount,
                principal_change=entry.principal_change,
                interest_change=entry.interest_change,
                outstanding_debt=entry.outstanding_debt,
                created_at=entry.created_at,
            )
            for entry in entries
        ],
        recent_playing_income_entries=[
            PlayingIncomeEntryResponse(
                id=entry.id,
                match_id=entry.match_id,
                match_result=entry.match_result,
                match_duration_seconds=entry.match_duration_seconds,
                match_completed_at=entry.match_completed_at,
                share_price=entry.share_price,
                base_rate=entry.base_rate,
                outcome_multiplier=entry.outcome_multiplier,
                amount=entry.amount,
                created_at=entry.created_at,
            )
            for entry in playing_income.recent_entries
        ],
    )


@router.get("/bank", response_model=BankSummaryResponse)
async def get_bank_summary(
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> BankSummaryResponse:
    return await _build_bank_summary(session, user, as_of=datetime.now(UTC))


@router.post("/bank/borrow", response_model=BankSummaryResponse)
async def borrow_from_bank(
    body: BankActionRequest,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> BankSummaryResponse:
    now = datetime.now(UTC)
    await apply_due_interest(session, user, as_of=now)
    snapshot = await build_account_snapshot(session, user, as_of=now)
    amount = round_currency(body.amount)

    if amount > snapshot.available_credit:
        raise HTTPException(
            status_code=400,
            detail="Borrow amount exceeds available credit",
        )

    session.add(apply_borrow(user, amount, at=now))
    session.add(apply_borrow_interest(user, amount, at=now))
    await record_user_wealth_snapshot(
        session,
        user,
        source=UserWealthSnapshotSource.CREDIT_ACTION,
        as_of=now,
    )
    await session.commit()
    await session.refresh(user)
    return await _build_bank_summary(session, user, as_of=now)


@router.post("/bank/repay", response_model=BankSummaryResponse)
async def repay_bank_debt(
    body: BankActionRequest,
    user: CurrentOnboardedUser,
    session: SessionDep,
) -> BankSummaryResponse:
    now = datetime.now(UTC)
    await apply_due_interest(session, user, as_of=now)
    outstanding = current_outstanding_debt(user)
    if outstanding <= 0:
        raise HTTPException(status_code=400, detail="No outstanding debt to repay")

    amount = round_currency(min(body.amount, outstanding))
    if amount > user.balance:
        raise HTTPException(
            status_code=400,
            detail="Insufficient balance to repay debt",
        )

    session.add(apply_repayment(user, amount, at=now))
    await record_user_wealth_snapshot(
        session,
        user,
        source=UserWealthSnapshotSource.CREDIT_ACTION,
        as_of=now,
    )
    await session.commit()
    await session.refresh(user)
    return await _build_bank_summary(session, user, as_of=now)
