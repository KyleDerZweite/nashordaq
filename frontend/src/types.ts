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
export type PoroSpawnStatus = "ACTIVE" | "CLAIMED" | "EXPIRED";
export type UserWealthSnapshotSource =
  | "ONBOARDING"
  | "MARKET_UPDATE"
  | "CREDIT_ACTION";

export interface UserResponse {
  id: number;
  email: string;
  display_name: string;
  role: "player" | "admin";
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
  rescue_loan_amount: number;
  rescue_loan_uses_remaining: number;
  rescue_loan_interest_rate: number;
  rescue_loan_upfront_interest_amount: number;
  rescue_net_worth_threshold: number;
  rescue_loan_available: boolean;
  rescue_loan_block_reason: string | null;
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
}

export interface UserProfileUpdate {
  game_name: string;
  tag_line: string;
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
  player_game_name: string;
  user_name: string | null;
  user_game_name: string | null;
  side: OrderSide;
  quantity: number;
  status: OrderStatus;
  source: OrderSource;
  execution_price: number | null;
  market_impact_pct: number | null;
  price_after_impact: number | null;
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
  player_game_name: string;
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
  player_game_name: string;
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

export interface AdminOverviewResponse {
  total_users: number;
  onboarded_users: number;
  admin_users: number;
  tracked_players: number;
  total_orders: number;
  pending_orders: number;
  executed_orders: number;
  reverted_orders: number;
  cancelled_orders: number;
  total_cash_balance: number;
  total_debt_outstanding: number;
}

export interface AdminUserSummaryResponse {
  id: number;
  email: string;
  display_name: string;
  role: "player" | "admin";
  linked_player_id: number | null;
  linked_player_name: string | null;
  linked_player_game_name: string | null;
  onboarding_complete: boolean;
  balance: number;
  holdings_value: number;
  active_gamba_value: number;
  debt_outstanding: number;
  total_value: number;
  created_at: string;
}

export interface AdminUserPortfolioResponse {
  user_id: number;
  email: string;
  display_name: string;
  role: "player" | "admin";
  linked_player_id: number | null;
  linked_player_name: string | null;
  linked_player_game_name: string | null;
  onboarding_complete: boolean;
  created_at: string;
  rescue_loan_uses_remaining: number;
  rescue_loan_available: boolean;
  rescue_loan_block_reason: string | null;
  portfolio: PortfolioResponse;
}

export interface AdminPlayerPlayingIncomeEntryResponse {
  match_id: string;
  match_result: PlayingIncomeMatchResult;
  match_completed_at: string;
  amount: number;
  share_price: number;
  outcome_multiplier: number;
}

export interface AdminPlayerPoroRewardResponse {
  spawn_id: string;
  reward_amount: number;
  spawned_at: string;
  claimed_at: string | null;
  status: PoroSpawnStatus;
}

export type PlayerMatchLpSource = "OBSERVED" | "ESTIMATED";

export interface AdminPlayerMatchResponse {
  match_id: string;
  win: boolean;
  lp_delta: number;
  lp_delta_source: PlayerMatchLpSource;
  price_before: number;
  price_after: number;
  playing_income_amount: number | null;
  completed_at: string;
}

export interface AdminPlayerInsightResponse {
  player_id: number;
  display_name: string;
  game_name: string;
  tag_line: string;
  linked_user_id: number | null;
  linked_user_display_name: string | null;
  linked_user_balance: number | null;
  linked_user_holdings_value: number | null;
  linked_user_active_gamba_value: number | null;
  linked_user_debt_outstanding: number | null;
  linked_user_net_worth: number | null;
  current_price: number;
  lp_abs: number;
  previous_lp_abs: number;
  lp_delta: number;
  streak: number;
  effective_positive_streak: number;
  ranked_wins_snapshot: number | null;
  ranked_losses_snapshot: number | null;
  estimated_win_rate: number | null;
  avg_lp_gain_on_win: number | null;
  avg_lp_loss_on_loss: number | null;
  estimated_lp_ratio_raw: number | null;
  estimated_lp_ratio_clamped: number;
  estimated_streak_multiplier: number;
  shareholder_count: number;
  total_shares_held: number;
  active_gamba_positions: number;
  active_gamba_cash: number;
  playing_income_game_count: number;
  playing_income_lifetime_total: number;
  playing_income_average_per_game: number | null;
  playing_income_last_24h: number;
  poro_claim_count: number;
  poro_rewards_total: number;
  recent_player_matches: AdminPlayerMatchResponse[];
  recent_playing_income_entries: AdminPlayerPlayingIncomeEntryResponse[];
  recent_poro_rewards: AdminPlayerPoroRewardResponse[];
}

export interface LeaderboardEntry {
  user_id: number;
  display_name: string;
  game_name: string;
  total_value: number;
  rank: number;
}

export interface LeaderboardPlayerPortfolioResponse {
  display_name: string;
  game_name: string;
  total_value: number;
  holdings: HoldingResponse[];
}

export interface SystemStatusResponse {
  service_status: "ok";
  scheduler_running: boolean;
  market_status: MarketStatus;
  tracked_player_count: number;
  expected_update_interval_minutes: number;
  last_market_update_at: string | null;
  gamba_enabled: boolean;
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
  inactive: boolean;
}

export interface MarketAccountResponse {
  game_name: string;
  tag_line: string;
  puuid: string;
}

export interface PoroSpawnResponse {
  spawn_id: string;
  tier: number;
  tier_label: string;
  reward_amount: number;
  asset_key: string;
  start_x: number;
  start_y: number;
  end_x: number;
  end_y: number;
  duration_ms: number;
  spawned_at: string;
  expires_at: string;
  status: PoroSpawnStatus;
}

export interface PoroStateResponse {
  enabled: boolean;
  server_time: string;
  next_roll_at: string | null;
  active_spawn: PoroSpawnResponse | null;
}

export interface PoroClaimRequest {
  spawn_id: string;
}

export interface PoroClaimResponse {
  spawn_id: string;
  tier: number;
  reward_amount: number;
  claimed_at: string;
  balance: number;
}

export interface SimulationMatch {
  delta_lp: number;
  win: boolean;
}

export interface SimulationParameterSet {
  label: string;
  pricing_alpha?: number | null;
  pricing_loss_move_multiplier?: number | null;
  pricing_max_effective_streak?: number | null;
  pricing_positive_lp_soft_cap?: number | null;
  pricing_negative_lp_soft_cap?: number | null;
  pricing_positive_lp_excess_efficiency?: number | null;
  pricing_negative_lp_excess_efficiency?: number | null;
  pricing_win_streak_lp_ratio_default?: number | null;
}

export interface SimulationRequest {
  matches?: SimulationMatch[] | null;
  player_id?: number | null;
  starting_price: number;
  starting_streak: number;
  parameter_sets: SimulationParameterSet[];
}

export interface SimulationStep {
  match_index: number;
  delta_lp: number;
  win: boolean;
  streak_before: number;
  streak_after: number;
  price_before: number;
  price_after: number;
  effective_delta_lp: number;
  streak_multiplier: number;
  price_move: number;
}

export interface SimulationTrajectory {
  label: string;
  parameters: Record<string, number>;
  steps: SimulationStep[];
}

export interface SimulationResponse {
  results: SimulationTrajectory[];
}

export interface SimulationDefaultsResponse {
  pricing_alpha: number;
  pricing_loss_move_multiplier: number;
  pricing_max_effective_streak: number;
  pricing_positive_lp_soft_cap: number;
  pricing_negative_lp_soft_cap: number;
  pricing_positive_lp_excess_efficiency: number;
  pricing_negative_lp_excess_efficiency: number;
  pricing_win_streak_lp_ratio_default: number;
}

export interface SimulationPlayerMatchResponse {
  match_id: string;
  win: boolean;
  lp_delta: number;
  streak_before: number;
  streak_after: number;
  price_before: number;
  price_after: number;
  completed_at: string;
}
