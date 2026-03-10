/* -------------------------------------------------------
 * Types mirroring backend Pydantic schemas (app/schemas.py).
 * Keep in sync with the backend response models.
 * ------------------------------------------------------- */

export type OrderSide = "BUY" | "SELL";
export type OrderStatus = "PENDING" | "EXECUTED" | "CANCELLED" | "REVERTED";
export type PlayerTrend = "up" | "down" | "flat";
export type MarketStatus = "healthy" | "degraded" | "idle";

export interface UserResponse {
  id: number;
  username: string;
  role: "player" | "spectator";
  balance: number;
  linked_player_id: number | null;
  onboarding_complete: boolean;
  created_at: string;
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
  execution_price: number | null;
  created_at: string;
  executed_at: string | null;
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
