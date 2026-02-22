import type {
  PlayerSummary,
  LeaderboardEntry,
  HoldingResponse,
  OrderResponse,
  UserResponse,
} from "../types";

/* -------------------------------------------------------
 * Mock data for the design scaffold.
 * Shapes match backend API responses exactly.
 * ------------------------------------------------------- */

export const MOCK_PLAYERS: PlayerSummary[] = [
  {
    id: 1,
    display_name: "Faker",
    game_name: "Faker",
    tag_line: "KR1",
    current_price: 42.85,
    last_updated: "2026-02-22T14:30:00Z",
  },
  {
    id: 2,
    display_name: "Zeus",
    game_name: "Zeus",
    tag_line: "KR1",
    current_price: 31.2,
    last_updated: "2026-02-22T14:28:00Z",
  },
  {
    id: 3,
    display_name: "Oner",
    game_name: "Oner",
    tag_line: "KR1",
    current_price: 27.55,
    last_updated: "2026-02-22T14:25:00Z",
  },
  {
    id: 4,
    display_name: "Gumayusi",
    game_name: "Gumayusi",
    tag_line: "KR1",
    current_price: 29.1,
    last_updated: "2026-02-22T14:22:00Z",
  },
  {
    id: 5,
    display_name: "Keria",
    game_name: "Keria",
    tag_line: "KR1",
    current_price: 33.4,
    last_updated: "2026-02-22T14:20:00Z",
  },
  {
    id: 6,
    display_name: "Chovy",
    game_name: "Chovy",
    tag_line: "KR1",
    current_price: 38.9,
    last_updated: "2026-02-22T14:18:00Z",
  },
];

/** Price deltas for the mock display (not a backend field; computed client-side). */
export const MOCK_DELTAS: Record<number, number> = {
  1: +2.35,
  2: -1.05,
  3: +0.8,
  4: -0.45,
  5: +1.6,
  6: +3.1,
};

export const MOCK_LEADERBOARD: LeaderboardEntry[] = [
  { username: "kyle", total_value: 12480.5, rank: 1 },
  { username: "jordan", total_value: 11230.0, rank: 2 },
  { username: "alex", total_value: 10890.75, rank: 3 },
  { username: "sam", total_value: 10150.25, rank: 4 },
];

export const MOCK_HOLDINGS: HoldingResponse[] = [
  {
    player_id: 1,
    player_name: "Faker",
    quantity: 15,
    current_price: 42.85,
    market_value: 642.75,
  },
  {
    player_id: 5,
    player_name: "Keria",
    quantity: 10,
    current_price: 33.4,
    market_value: 334.0,
  },
  {
    player_id: 6,
    player_name: "Chovy",
    quantity: 8,
    current_price: 38.9,
    market_value: 311.2,
  },
];

export const MOCK_ORDERS: OrderResponse[] = [
  {
    id: 101,
    player_id: 1,
    player_name: "Faker",
    side: "BUY",
    quantity: 5,
    status: "EXECUTED",
    execution_price: 40.5,
    created_at: "2026-02-22T12:00:00Z",
    executed_at: "2026-02-22T12:00:01Z",
  },
  {
    id: 102,
    player_id: 3,
    player_name: "Oner",
    side: "SELL",
    quantity: 3,
    status: "PENDING",
    execution_price: null,
    created_at: "2026-02-22T13:45:00Z",
    executed_at: null,
  },
];

export const MOCK_BALANCE = 11_503.55;

export const MOCK_USER: UserResponse = {
  id: 1,
  username: "kyle",
  balance: 11_503.55,
  created_at: "2026-01-15T08:00:00Z",
};
