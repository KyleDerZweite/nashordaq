import enum
from datetime import datetime

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class OrderSide(enum.StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(enum.StrEnum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REVERTED = "REVERTED"


class OrderSource(enum.StrEnum):
    MANUAL = "MANUAL"
    GAMBA = "GAMBA"


class GambaStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    SETTLED = "SETTLED"


class BankLedgerEntryType(enum.StrEnum):
    BORROW = "BORROW"
    INTEREST = "INTEREST"
    REPAYMENT = "REPAYMENT"


class PlayingIncomeMatchResult(enum.StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"


class PoroTier(enum.StrEnum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"
    TIER_5 = "TIER_5"
    TIER_6 = "TIER_6"


class PoroSpawnStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    CLAIMED = "CLAIMED"
    EXPIRED = "EXPIRED"


class UserWealthSnapshotSource(enum.StrEnum):
    ONBOARDING = "ONBOARDING"
    MARKET_UPDATE = "MARKET_UPDATE"
    CREDIT_ACTION = "CREDIT_ACTION"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    balance: Mapped[float] = mapped_column(Float, default=1000.0)
    debt_principal: Mapped[float] = mapped_column(Float, default=0.0)
    debt_accrued_interest: Mapped[float] = mapped_column(Float, default=0.0)
    debt_last_accrued_at: Mapped[datetime | None] = mapped_column(default=None)
    debt_next_accrual_at: Mapped[datetime | None] = mapped_column(
        default=None,
        index=True,
    )
    rescue_loan_uses_remaining: Mapped[int] = mapped_column(Integer, default=1)
    linked_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("tracked_players.id"), unique=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())

    holdings: Mapped[list["Holding"]] = relationship(back_populates="user")
    holding_lots: Mapped[list["HoldingLot"]] = relationship(back_populates="user")
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    gamba_positions: Mapped[list["GambaPosition"]] = relationship(back_populates="user")
    bank_ledger_entries: Mapped[list["BankLedgerEntry"]] = relationship(
        back_populates="user"
    )
    wealth_snapshots: Mapped[list["UserWealthSnapshot"]] = relationship(
        back_populates="user"
    )
    poro_spawns: Mapped[list["PoroSpawn"]] = relationship(back_populates="user")
    poro_state: Mapped["UserPoroState | None"] = relationship(
        back_populates="user",
        uselist=False,
        foreign_keys="UserPoroState.user_id",
    )
    linked_player: Mapped["TrackedPlayer | None"] = relationship(
        foreign_keys=[linked_player_id],
        back_populates="linked_users",
    )


class TrackedPlayer(Base):
    __tablename__ = "tracked_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_name: Mapped[str] = mapped_column(String(255))
    tag_line: Mapped[str] = mapped_column(String(10))
    display_name: Mapped[str] = mapped_column(String(255))
    puuid: Mapped[str | None] = mapped_column(String(255), default=None)
    summoner_id: Mapped[str | None] = mapped_column(String(255), default=None)
    current_price: Mapped[float] = mapped_column(Float, default=10.0)
    lp_abs: Mapped[int] = mapped_column(Integer, default=0)
    previous_lp_abs: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    gamma_factor: Mapped[float] = mapped_column(Float, default=1.0)
    last_updated: Mapped[datetime | None] = mapped_column(default=None)
    last_playing_income_match_id: Mapped[str | None] = mapped_column(
        String(64), default=None
    )
    last_playing_income_match_end_at: Mapped[datetime | None] = mapped_column(
        default=None,
        index=True,
    )

    __table_args__ = (
        UniqueConstraint("game_name", "tag_line", name="uq_player_riot_id"),
    )

    holdings: Mapped[list["Holding"]] = relationship(back_populates="player")
    holding_lots: Mapped[list["HoldingLot"]] = relationship(back_populates="player")
    orders: Mapped[list["Order"]] = relationship(back_populates="player")
    gamba_positions: Mapped[list["GambaPosition"]] = relationship(
        back_populates="player"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(back_populates="player")
    playing_income_entries: Mapped[list["PlayingIncomeEntry"]] = relationship(
        back_populates="player"
    )
    linked_users: Mapped[list["User"]] = relationship(
        back_populates="linked_player",
        foreign_keys="User.linked_player_id",
    )


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "player_id", name="uq_user_player"),)

    user: Mapped["User"] = relationship(back_populates="holdings")
    player: Mapped["TrackedPlayer"] = relationship(back_populates="holdings")


class HoldingLot(Base):
    __tablename__ = "holding_lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    buy_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), index=True, default=None
    )
    quantity: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(insert_default=func.now(), index=True)

    user: Mapped["User"] = relationship(back_populates="holding_lots")
    player: Mapped["TrackedPlayer"] = relationship(back_populates="holding_lots")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    quantity: Mapped[int] = mapped_column(Integer)
    quantity_value: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus), default=OrderStatus.PENDING
    )
    source: Mapped[OrderSource] = mapped_column(
        Enum(OrderSource), default=OrderSource.MANUAL
    )
    execution_price: Mapped[float | None] = mapped_column(Float, default=None)
    gross_execution_price: Mapped[float | None] = mapped_column(Float, default=None)
    gross_total_value: Mapped[float | None] = mapped_column(Float, default=None)
    entry_total_value: Mapped[float | None] = mapped_column(Float, default=None)
    adjustment_value: Mapped[float | None] = mapped_column(Float, default=None)
    adjustment_reason: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())
    executed_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped["User"] = relationship(back_populates="orders")
    player: Mapped["TrackedPlayer"] = relationship(back_populates="orders")
    transaction: Mapped["Transaction | None"] = relationship(
        back_populates="order", uselist=False
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    quantity: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Float)
    total: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="transaction")


class GambaPosition(Base):
    __tablename__ = "gamba_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    buy_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), default=None
    )
    sell_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id"), default=None
    )
    cash_amount: Mapped[float] = mapped_column(Float)
    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    scheduled_settlement_at: Mapped[datetime] = mapped_column(index=True)
    settlement_multiplier: Mapped[float] = mapped_column(Float)
    status: Mapped[GambaStatus] = mapped_column(
        Enum(GambaStatus), default=GambaStatus.ACTIVE, index=True
    )
    exit_price: Mapped[float | None] = mapped_column(Float, default=None)
    settled_at: Mapped[datetime | None] = mapped_column(default=None)
    raw_pnl: Mapped[float | None] = mapped_column(Float, default=None)
    settled_pnl: Mapped[float | None] = mapped_column(Float, default=None)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now())

    user: Mapped["User"] = relationship(back_populates="gamba_positions")
    player: Mapped["TrackedPlayer"] = relationship(back_populates="gamba_positions")


class BankLedgerEntry(Base):
    __tablename__ = "bank_ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    entry_type: Mapped[BankLedgerEntryType] = mapped_column(Enum(BankLedgerEntryType))
    amount: Mapped[float] = mapped_column(Float)
    principal_change: Mapped[float] = mapped_column(Float, default=0.0)
    interest_change: Mapped[float] = mapped_column(Float, default=0.0)
    outstanding_debt: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now(), index=True)

    user: Mapped["User"] = relationship(back_populates="bank_ledger_entries")


class PlayingIncomeEntry(Base):
    __tablename__ = "playing_income_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    match_id: Mapped[str] = mapped_column(String(64))
    match_result: Mapped[PlayingIncomeMatchResult] = mapped_column(
        Enum(PlayingIncomeMatchResult)
    )
    match_duration_seconds: Mapped[int] = mapped_column(Integer)
    match_completed_at: Mapped[datetime] = mapped_column(index=True)
    share_price: Mapped[float] = mapped_column(Float)
    base_rate: Mapped[float] = mapped_column(Float)
    outcome_multiplier: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(insert_default=func.now(), index=True)

    __table_args__ = (
        UniqueConstraint("player_id", "match_id", name="uq_playing_income_match"),
    )

    user: Mapped["User"] = relationship()
    player: Mapped["TrackedPlayer"] = relationship(
        back_populates="playing_income_entries"
    )


class PoroSpawn(Base):
    __tablename__ = "poro_spawns"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    tier: Mapped[PoroTier] = mapped_column(Enum(PoroTier))
    reward_amount: Mapped[float] = mapped_column(Float)
    asset_key: Mapped[str] = mapped_column(String(32))
    start_x: Mapped[float] = mapped_column(Float)
    start_y: Mapped[float] = mapped_column(Float)
    end_x: Mapped[float] = mapped_column(Float)
    end_y: Mapped[float] = mapped_column(Float)
    duration_ms: Mapped[int] = mapped_column(Integer)
    spawned_at: Mapped[datetime] = mapped_column(insert_default=func.now(), index=True)
    expires_at: Mapped[datetime] = mapped_column(index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(default=None)
    status: Mapped[PoroSpawnStatus] = mapped_column(
        Enum(PoroSpawnStatus),
        default=PoroSpawnStatus.ACTIVE,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="poro_spawns")
    state_links: Mapped[list["UserPoroState"]] = relationship(
        back_populates="active_spawn",
        foreign_keys="UserPoroState.active_spawn_id",
    )


class UserPoroState(Base):
    __tablename__ = "user_poro_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, index=True
    )
    next_roll_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    active_spawn_id: Mapped[int | None] = mapped_column(
        ForeignKey("poro_spawns.id"),
        default=None,
    )
    updated_at: Mapped[datetime] = mapped_column(
        insert_default=func.now(),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(
        back_populates="poro_state",
        foreign_keys=[user_id],
    )
    active_spawn: Mapped["PoroSpawn | None"] = relationship(
        back_populates="state_links",
        foreign_keys=[active_spawn_id],
    )


class UserWealthSnapshot(Base):
    __tablename__ = "user_wealth_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[UserWealthSnapshotSource] = mapped_column(
        Enum(UserWealthSnapshotSource)
    )
    cash_balance: Mapped[float] = mapped_column(Float)
    holdings_value: Mapped[float] = mapped_column(Float)
    active_gamba_value: Mapped[float] = mapped_column(Float)
    debt_outstanding: Mapped[float] = mapped_column(Float)
    net_worth: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(insert_default=func.now(), index=True)

    user: Mapped["User"] = relationship(back_populates="wealth_snapshots")


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("tracked_players.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    lp_abs: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(insert_default=func.now())

    player: Mapped["TrackedPlayer"] = relationship(back_populates="price_history")
