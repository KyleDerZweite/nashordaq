/* -------------------------------------------------------
 * Types mirroring backend Pydantic schemas (app/schemas.py).
 * Keep in sync with the backend response models.
 * ------------------------------------------------------- */

export type OrderSide = "BUY" | "SELL";
export type OrderStatus = "PENDING" | "EXECUTED" | "CANCELLED" | "REVERTED";

export interface UserResponse {
  id: number;
  username: string;
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
  current_price: number;
  market_value: number;
}

export interface PortfolioResponse {
  balance: number;
  holdings: HoldingResponse[];
  total_value: number;
}

export interface LeaderboardEntry {
  username: string;
  total_value: number;
  rank: number;
}
