from datetime import datetime

from pydantic import BaseModel, Field

from app.models import OrderSide, OrderStatus


class UserResponse(BaseModel):
    id: int
    username: str
    balance: float
    created_at: datetime


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
    side: OrderSide
    quantity: int
    status: OrderStatus
    execution_price: float | None
    created_at: datetime
    executed_at: datetime | None


class HoldingResponse(BaseModel):
    player_id: int
    player_name: str
    quantity: int
    current_price: float
    market_value: float


class PortfolioResponse(BaseModel):
    balance: float
    holdings: list[HoldingResponse]
    total_value: float


class LeaderboardEntry(BaseModel):
    username: str
    total_value: float
    rank: int
