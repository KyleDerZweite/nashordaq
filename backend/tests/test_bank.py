from datetime import UTC, datetime, timedelta

import pytest

from app.models import User


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


async def test_bank_borrow_uses_credit_limit_and_keeps_net_worth_flat(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1000.0
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["credit_limit"] == pytest.approx(250.0)
    assert summary["available_credit"] == pytest.approx(250.0)

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 250})
    assert borrow_resp.status_code == 200
    borrowed = borrow_resp.json()
    assert borrowed["cash_balance"] == pytest.approx(1250.0)
    assert borrowed["debt_principal"] == pytest.approx(250.0)
    assert borrowed["debt_outstanding"] == pytest.approx(250.0)
    assert borrowed["debt_adjusted_net_worth"] == pytest.approx(1000.0)
    assert borrowed["available_credit"] == pytest.approx(0.0)

    portfolio_resp = await auth_client.get("/api/portfolio")
    assert portfolio_resp.status_code == 200
    assert portfolio_resp.json()["total_value"] == pytest.approx(1000.0)

    leaderboard_resp = await auth_client.get("/api/leaderboard")
    assert leaderboard_resp.status_code == 200
    assert leaderboard_resp.json()[0]["total_value"] == pytest.approx(1000.0)


async def test_bank_borrow_rejects_amount_above_available_credit(
    auth_client,
    db_session,
):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1000.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 300})
    assert borrow_resp.status_code == 400
    assert borrow_resp.json()["detail"] == "Borrow amount exceeds available credit"


async def test_bank_repayment_clears_interest_first(auth_client, db_session):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1000.0
    await db_session.commit()

    borrow_resp = await auth_client.post("/api/bank/borrow", json={"amount": 250})
    assert borrow_resp.status_code == 200

    user = await db_session.get(User, user_id)
    assert user is not None
    user.debt_accrued_interest = 10.0
    user.debt_next_accrual_at = datetime.now(UTC) + timedelta(hours=4)
    await db_session.commit()

    repay_resp = await auth_client.post("/api/bank/repay", json={"amount": 60})
    assert repay_resp.status_code == 200
    repaid = repay_resp.json()
    assert repaid["cash_balance"] == pytest.approx(1190.0)
    assert repaid["debt_principal"] == pytest.approx(200.0)
    assert repaid["debt_accrued_interest"] == pytest.approx(0.0)
    assert repaid["debt_outstanding"] == pytest.approx(200.0)


async def test_bank_summary_previews_due_interest(auth_client, db_session):
    await _onboard_bank_user(auth_client)

    me_resp = await auth_client.get("/api/user/me")
    user_id = me_resp.json()["id"]
    user = await db_session.get(User, user_id)
    assert user is not None
    user.balance = 1250.0
    user.debt_principal = 250.0
    user.debt_accrued_interest = 0.0
    user.debt_last_accrued_at = datetime.now(UTC) - timedelta(hours=72)
    user.debt_next_accrual_at = datetime.now(UTC) - timedelta(minutes=5)
    await db_session.commit()

    summary_resp = await auth_client.get("/api/bank")
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["debt_principal"] == pytest.approx(250.0)
    assert summary["debt_accrued_interest"] == pytest.approx(5.38)
    assert summary["debt_outstanding"] == pytest.approx(255.38)
