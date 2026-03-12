from datetime import UTC, datetime, timedelta

import pytest

from app.models import PlayingIncomeEntry, PlayingIncomeMatchResult, TrackedPlayer, User


async def _onboard_bank_user(auth_client):
    onboard_resp = await auth_client.post(
        "/api/user/onboarding",
        json={
            "game_name": "bank-user",
            "tag_line": "EUW",
            "display_name": "Bank User",
        },
    )
    assert onboard_resp.status_code == 200


async def test_bank_borrow_applies_immediate_interest_and_reduces_net_worth(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 200.0
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["rescue_loan_available"] is True
    assert summary["rescue_loan_amount"] == pytest.approx(750.0)
    assert summary["rescue_loan_uses_remaining"] == 1
    assert summary["rescue_loan_upfront_interest_amount"] == pytest.approx(15.0)

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 200
    borrowed = borrow_resp.json()
    assert borrowed["cash_balance"] == pytest.approx(950.0)
    assert borrowed["debt_principal"] == pytest.approx(750.0)
    assert borrowed["debt_accrued_interest"] == pytest.approx(15.0)
    assert borrowed["debt_outstanding"] == pytest.approx(765.0)
    assert borrowed["debt_adjusted_net_worth"] == pytest.approx(185.0)
    assert borrowed["rescue_loan_available"] is False
    assert borrowed["rescue_loan_uses_remaining"] == 0
    assert borrowed["rescue_loan_block_reason"] == (
        "Rescue loan unavailable while debt is outstanding"
    )
    assert borrowed["interest_rate_per_interval"] == pytest.approx(0.02)
    assert [entry["entry_type"] for entry in borrowed["recent_entries"][:2]] == [
        "INTEREST",
        "BORROW",
    ]

    portfolio_resp = await auth_client.get("/api/portfolio")
    assert portfolio_resp.status_code == 200
    assert portfolio_resp.json()["total_value"] == pytest.approx(185.0)

    leaderboard_resp = await auth_client.get("/api/leaderboard")
    assert leaderboard_resp.status_code == 200
    assert leaderboard_resp.json()[0]["total_value"] == pytest.approx(185.0)


async def test_bank_summary_locks_rescue_when_net_worth_is_above_threshold(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 4000.0
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["debt_adjusted_net_worth"] == pytest.approx(4000.0)
    assert summary["rescue_loan_available"] is False
    assert summary["rescue_loan_block_reason"] == (
        "Rescue loan unlocks once net worth falls to 250 P or below"
    )


async def test_bank_summary_unlocks_rescue_at_zero_net_worth(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 0.0
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["debt_adjusted_net_worth"] == pytest.approx(0.0)
    assert summary["rescue_loan_available"] is True
    assert summary["rescue_loan_amount"] == pytest.approx(750.0)
    assert summary["rescue_net_worth_threshold"] == pytest.approx(250.0)


async def test_bank_borrow_rejects_wrong_rescue_amount(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 200.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 550})
    assert borrow_resp.status_code == 400
    assert borrow_resp.json()["detail"] == "Rescue loan amount is fixed at 750.00 P"


async def test_bank_borrow_rejects_rescue_when_net_worth_is_too_high(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 400.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 400
    assert borrow_resp.json()["detail"] == (
        "Rescue loan unlocks once net worth falls to 250 P or below"
    )


async def test_bank_repayment_clears_interest_first(auth_client, db_session):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 200.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 200

    user = await db_session.get(User, user_id)
    assert user is not None
    user.debt_accrued_interest = 10.0
    user.debt_next_accrual_at = datetime.now(UTC) + timedelta(hours=4)
    await db_session.commit()

    repay_resp = await auth_client.post("/api/bank/repay", json={"amount": 60})
    assert repay_resp.status_code == 200
    repaid = repay_resp.json()
    assert repaid["cash_balance"] == pytest.approx(890.0)
    assert repaid["debt_principal"] == pytest.approx(700.0)
    assert repaid["debt_accrued_interest"] == pytest.approx(0.0)
    assert repaid["debt_outstanding"] == pytest.approx(700.0)


async def test_bank_rescue_cannot_be_taken_twice_while_debt_is_outstanding(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 100.0
    await db_session.commit()

    first_borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert first_borrow_resp.status_code == 200

    second_borrow_resp = await auth_client.post(
        "/api/bank/borrow", json={"amount": 750}
    )
    assert second_borrow_resp.status_code == 400
    assert second_borrow_resp.json()["detail"] == (
        "Rescue loan unavailable while debt is outstanding"
    )


async def test_bank_rescue_stays_spent_after_full_repayment(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 0.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 750})
    assert borrow_resp.status_code == 200

    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 900.0
    await db_session.commit()

    repay_resp = await auth_client.post("/api/bank/repay", json={"amount": 765})
    assert repay_resp.status_code == 200
    repaid = repay_resp.json()

    assert repaid["debt_outstanding"] == pytest.approx(0.0)
    assert repaid["rescue_loan_uses_remaining"] == 0
    assert repaid["rescue_loan_available"] is False
    assert repaid["rescue_loan_block_reason"] == (
        "Rescue loan already used. Ask an admin to restore it"
    )


async def test_bank_summary_previews_due_interest(auth_client, db_session):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1250.0
    user.debt_principal = 500.0
    user.debt_accrued_interest = 0.0
    user.debt_last_accrued_at = datetime.now(UTC) - timedelta(hours=120)
    user.debt_next_accrual_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["debt_principal"] == pytest.approx(500.0)
    assert summary["debt_accrued_interest"] == pytest.approx(10.0)
    assert summary["debt_outstanding"] == pytest.approx(510.0)
    assert summary["interest_rate_per_interval"] == pytest.approx(0.02)
    assert summary["next_interest_amount"] == pytest.approx(10.2)


async def test_bank_summary_uses_rescue_interest_rate_for_outstanding_debt(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1500.0
    user.debt_principal = 1200.0
    user.debt_accrued_interest = 0.0
    user.debt_last_accrued_at = datetime.now(UTC)
    user.debt_next_accrual_at = datetime.now(UTC) + timedelta(hours=4)
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["interest_rate_per_interval"] == pytest.approx(0.02)
    assert summary["next_interest_amount"] == pytest.approx(24.0)


async def test_bank_summary_includes_playing_income_metrics(auth_client, db_session):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1000.0
    player = await db_session.get(TrackedPlayer, user.linked_player_id)
    assert player is not None
    player.current_price = 42.0
    now = datetime.now(UTC)
    db_session.add_all(
        [
            PlayingIncomeEntry(
                user_id=user.id,
                player_id=player.id,
                match_id="EUW1_500",
                match_result=PlayingIncomeMatchResult.WIN,
                match_duration_seconds=1800,
                match_completed_at=now - timedelta(hours=2),
                share_price=40.0,
                base_rate=0.01,
                outcome_multiplier=1.0,
                amount=0.4,
            ),
            PlayingIncomeEntry(
                user_id=user.id,
                player_id=player.id,
                match_id="EUW1_499",
                match_result=PlayingIncomeMatchResult.LOSS,
                match_duration_seconds=1700,
                match_completed_at=now - timedelta(days=2),
                share_price=40.0,
                base_rate=0.01,
                outcome_multiplier=0.5,
                amount=0.2,
            ),
        ]
    )
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["projected_next_win_income"] == pytest.approx(0.5)
    assert summary["projected_next_loss_income"] == pytest.approx(0.25)
    assert summary["playing_income_last_24h"] == pytest.approx(0.4)
    assert summary["playing_income_lifetime_total"] == pytest.approx(0.6)
    assert [
        entry["match_id"] for entry in summary["recent_playing_income_entries"]
    ] == [
        "EUW1_500",
        "EUW1_499",
    ]


async def test_bank_summary_applies_minimum_playing_income_projection(
    auth_client, db_session
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    player = await db_session.get(TrackedPlayer, user.linked_player_id)
    assert player is not None
    player.current_price = 8.0
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["projected_next_win_income"] == pytest.approx(0.23)
    assert summary["projected_next_loss_income"] == pytest.approx(0.12)
