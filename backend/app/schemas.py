from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import (
    BankLedgerEntryType,
    GambaStatus,
    OrderSide,
    OrderSource,
    OrderStatus,
    PlayingIncomeMatchResult,
    PoroSpawnStatus,
    UserWealthSnapshotSource,
)

UserRole = Literal["player", "admin"]
PlayerTrend = Literal["up", "down", "flat"]
MarketStatus = Literal["healthy", "degraded", "idle"]


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    balance: float
    linked_player_id: int | None
    onboarding_complete: bool
    created_at: datetime


class BankLedgerEntryResponse(BaseModel):
    id: int
    entry_type: BankLedgerEntryType
    amount: float
    principal_change: float
    interest_change: float
    outstanding_debt: float
    created_at: datetime


class BankActionRequest(BaseModel):
    amount: float = Field(gt=0)


class PlayingIncomeEntryResponse(BaseModel):
    id: int
    match_id: str
    match_result: PlayingIncomeMatchResult
    match_duration_seconds: int
    match_completed_at: datetime
    share_price: float
    base_rate: float
    outcome_multiplier: float
    amount: float
    created_at: datetime


class BankSummaryResponse(BaseModel):
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
    interest_interval_hours: float
    projected_next_win_income: float
    projected_next_loss_income: float
    playing_income_last_24h: float
    playing_income_lifetime_total: float
    recent_entries: list[BankLedgerEntryResponse]
    recent_playing_income_entries: list[PlayingIncomeEntryResponse]


class UserWealthSnapshotResponse(BaseModel):
    id: int
    source: UserWealthSnapshotSource
    cash_balance: float
    holdings_value: float
    active_gamba_value: float
    debt_outstanding: float
    net_worth: float
    recorded_at: datetime


class BalanceInsightsResponse(BaseModel):
    cash_balance: float
    holdings_value: float
    active_gamba_value: float
    debt_outstanding: float
    net_worth: float
    playing_income_last_24h: float
    playing_income_lifetime_total: float
    history: list[UserWealthSnapshotResponse]


class UserOnboardingCreate(BaseModel):
    game_name: str = Field(min_length=1, max_length=255)
    tag_line: str = Field(min_length=1, max_length=10)
    display_name: str = Field(min_length=1, max_length=255)


class UserProfileUpdate(BaseModel):
    game_name: str = Field(min_length=1, max_length=255)
    tag_line: str = Field(min_length=1, max_length=10)
    display_name: str = Field(min_length=1, max_length=255)


class PriceHistoryEntry(BaseModel):
    price: float
    lp_abs: int
    recorded_at: datetime


class PlayerSummary(BaseModel):
    id: int
    display_name: str
    game_name: str
    tag_line: str
    current_price: float
    trend: PlayerTrend
    last_updated: datetime | None


class PlayerDetail(PlayerSummary):
    previous_lp_abs: int
    lp_abs: int
    streak: int
    price_history: list[PriceHistoryEntry]


class OrderCreate(BaseModel):
    player_id: int
    side: OrderSide
    quantity: int = Field(gt=0)


class OrderResponse(BaseModel):
    id: int
    player_id: int
    player_name: str
    user_name: str | None = None
    side: OrderSide
    quantity: float
    status: OrderStatus
    source: OrderSource
    execution_price: float | None
    created_at: datetime
    executed_at: datetime | None


class OrderDetailResponse(OrderResponse):
    total_value: float | None
    gross_execution_price: float | None
    gross_total_value: float | None
    entry_total_value: float | None
    adjustment_value: float | None
    adjustment_reason: str | None


class GambaCreate(BaseModel):
    cash_amount: float = Field(gt=0)


class GambaPositionResponse(BaseModel):
    id: int
    player_id: int
    player_name: str
    cash_amount: float
    quantity: float
    entry_price: float
    scheduled_settlement_at: datetime
    settlement_multiplier: float
    status: GambaStatus
    exit_price: float | None
    settled_at: datetime | None
    raw_pnl: float | None
    settled_pnl: float | None
    created_at: datetime


class HoldingResponse(BaseModel):
    player_id: int
    player_name: str
    quantity: int
    average_buy_price: float
    current_price: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class PortfolioResponse(BaseModel):
    balance: float
    holdings_value: float
    active_gamba_value: float
    debt_outstanding: float
    holdings: list[HoldingResponse]
    total_value: float


class AdminOverviewResponse(BaseModel):
    total_users: int
    onboarded_users: int
    admin_users: int
    tracked_players: int
    total_orders: int
    pending_orders: int
    executed_orders: int
    reverted_orders: int
    cancelled_orders: int
    total_cash_balance: float
    total_debt_outstanding: float


class AdminUserSummaryResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    linked_player_id: int | None
    linked_player_name: str | None
    onboarding_complete: bool
    balance: float
    holdings_value: float
    active_gamba_value: float
    debt_outstanding: float
    total_value: float
    created_at: datetime


class AdminUserPortfolioResponse(BaseModel):
    user_id: int
    username: str
    role: UserRole
    linked_player_id: int | None
    linked_player_name: str | None
    onboarding_complete: bool
    created_at: datetime
    rescue_loan_uses_remaining: int
    rescue_loan_available: bool
    rescue_loan_block_reason: str | None
    portfolio: PortfolioResponse


class LeaderboardEntry(BaseModel):
    display_name: str
    total_value: float
    rank: int


class SystemStatusResponse(BaseModel):
    service_status: Literal["ok"]
    scheduler_running: bool
    market_status: MarketStatus
    tracked_player_count: int
    expected_update_interval_minutes: int
    last_market_update_at: datetime | None


class MarketAccountResponse(BaseModel):
    game_name: str
    tag_line: str
    puuid: str


class PoroSpawnResponse(BaseModel):
    spawn_id: str
    tier: int
    tier_label: str
    reward_amount: float
    asset_key: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    duration_ms: int
    spawned_at: datetime
    expires_at: datetime
    status: PoroSpawnStatus


class PoroStateResponse(BaseModel):
    enabled: bool
    server_time: datetime
    next_roll_at: datetime | None
    active_spawn: PoroSpawnResponse | None


class PoroClaimRequest(BaseModel):
    spawn_id: str = Field(min_length=1, max_length=32)


class PoroClaimResponse(BaseModel):
    spawn_id: str
    tier: int
    reward_amount: float
    claimed_at: datetime
    balance: float
