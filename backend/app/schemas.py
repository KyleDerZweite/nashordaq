from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import GambaStatus, OrderSide, OrderSource, OrderStatus

UserRole = Literal["player", "spectator"]
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
    holdings: list[HoldingResponse]
    total_value: float


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
