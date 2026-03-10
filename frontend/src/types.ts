/* -------------------------------------------------------
 * Types mirroring backend Pydantic schemas (app/schemas.py).
 * Keep in sync with the backend response models.
 * ------------------------------------------------------- */

export type OrderSide = "BUY" | "SELL";
export type OrderStatus = "PENDING" | "EXECUTED" | "CANCELLED" | "REVERTED";
export type OrderSource = "MANUAL" | "GAMBA";
export type PlayerTrend = "up" | "down" | "flat";
export type MarketStatus = "healthy" | "degraded" | "idle";
export type GambaStatus = "ACTIVE" | "SETTLED";
export type BankLedgerEntryType = "BORROW" | "INTEREST" | "REPAYMENT";
export type PlayingIncomeMatchResult = "WIN" | "LOSS";
export type UserWealthSnapshotSource =
  | "ONBOARDING"
  | "MARKET_UPDATE"
  | "CREDIT_ACTION";

export interface UserResponse {
  id: number;
  username: string;
  role: "player" | "spectator";
  balance: number;
  linked_player_id: number | null;
  onboarding_complete: boolean;
  created_at: string;
}

export interface BankActionRequest {
  amount: number;
}

export interface BankLedgerEntryResponse {
  id: number;
  entry_type: BankLedgerEntryType;
  amount: number;
  principal_change: number;
  interest_change: number;
  outstanding_debt: number;
  created_at: string;
}

export interface BankSummaryResponse {
  cash_balance: number;
  holdings_value: number;
  active_gamba_value: number;
  debt_principal: number;
  debt_accrued_interest: number;
  debt_outstanding: number;
  debt_adjusted_net_worth: number;
  credit_limit: number;
  available_credit: number;
  next_interest_accrual_at: string | null;
  next_interest_amount: number;
  interest_rate_per_interval: number;
  interest_interval_hours: number;
  projected_next_win_income: number;
  projected_next_loss_income: number;
  playing_income_last_24h: number;
  playing_income_lifetime_total: number;
  recent_entries: BankLedgerEntryResponse[];
  recent_playing_income_entries: PlayingIncomeEntryResponse[];
}

export interface PlayingIncomeEntryResponse {
  id: number;
  match_id: string;
  match_result: PlayingIncomeMatchResult;
  match_duration_seconds: number;
  match_completed_at: string;
  share_price: number;
  base_rate: number;
  outcome_multiplier: number;
  amount: number;
  created_at: string;
}

export interface UserWealthSnapshotResponse {
  id: number;
  source: UserWealthSnapshotSource;
  cash_balance: number;
  holdings_value: number;
  active_gamba_value: number;
  debt_outstanding: number;
  net_worth: number;
  recorded_at: string;
}

export interface BalanceInsightsResponse {
  cash_balance: number;
  holdings_value: number;
  active_gamba_value: number;
  debt_outstanding: number;
  net_worth: number;
  playing_income_last_24h: number;
  playing_income_lifetime_total: number;
  history: UserWealthSnapshotResponse[];
}

export interface UserOnboardingCreate {
  game_name: string;
  tag_line: string;
  display_name: string;
}

export interface UserProfileUpdate {
  game_name: string;
  tag_line: string;
  display_name: string;
}

export interface PriceHistoryEntry {
  price: number;
  lp_abs: number;
  recorded_at: string;
}

export interface PlayerSummary {
  id: number;
  display_name: string;
  game_name: string;
  tag_line: string;
  current_price: number;
  trend: PlayerTrend;
  last_updated: string | null;
}

export interface PlayerDetail extends PlayerSummary {
  previous_lp_abs: number;
  lp_abs: number;
  streak: number;
  price_history: PriceHistoryEntry[];
}

export interface OrderCreate {
  player_id: number;
  side: OrderSide;
  quantity: number;
}

export interface OrderResponse {
  id: number;
  player_id: number;
  player_name: string;
  user_name: string | null;
  side: OrderSide;
  quantity: number;
  status: OrderStatus;
  source: OrderSource;
  execution_price: number | null;
  created_at: string;
  executed_at: string | null;
}

export interface OrderDetailResponse extends OrderResponse {
  total_value: number | null;
  gross_execution_price: number | null;
  gross_total_value: number | null;
  entry_total_value: number | null;
  adjustment_value: number | null;
  adjustment_reason: string | null;
}

export interface GambaCreate {
  cash_amount: number;
}

export interface GambaPositionResponse {
  id: number;
  player_id: number;
  player_name: string;
  cash_amount: number;
  quantity: number;
  entry_price: number;
  scheduled_settlement_at: string;
  settlement_multiplier: number;
  status: GambaStatus;
  exit_price: number | null;
  settled_at: string | null;
  raw_pnl: number | null;
  settled_pnl: number | null;
  created_at: string;
}

export interface HoldingResponse {
  player_id: number;
  player_name: string;
  quantity: number;
  average_buy_price: number;
  current_price: number;
  cost_basis: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface PortfolioResponse {
  balance: number;
  holdings_value: number;
  active_gamba_value: number;
  debt_outstanding: number;
  holdings: HoldingResponse[];
  total_value: number;
}

export interface LeaderboardEntry {
  display_name: string;
  total_value: number;
  rank: number;
}

export interface SystemStatusResponse {
  service_status: "ok";
  scheduler_running: boolean;
  market_status: MarketStatus;
  tracked_player_count: number;
  expected_update_interval_minutes: number;
  last_market_update_at: string | null;
}

export interface MarketQuoteResponse {
  gameName: string;
  tagLine: string;
  tier: string;
  rank: string;
  leaguePoints: number;
  wins: number;
  losses: number;
  hotStreak: boolean;
  veteran: boolean;
  inactive: boolean;
  freshBlood: boolean;
}

export interface MarketAccountResponse {
  game_name: string;
  tag_line: string;
  puuid: string;
}
