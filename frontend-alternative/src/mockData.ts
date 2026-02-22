export type MockPlayer = {
  id: number;
  display_name: string;
  game_name: string;
  tag_line: string;
  current_price: number;
  last_updated: string | null;
  lp_signal_24h: number;
};

export type MockUser = {
  id: number;
  username: string;
  balance: number;
  created_at: string;
};

export type MockOrder = {
  id: number;
  player_id: number;
  player_name: string;
  side: "BUY" | "SELL";
  quantity: number;
  status: "PENDING" | "FILLED" | "CANCELLED";
  execution_price: number | null;
  created_at: string;
  executed_at: string | null;
};

export type MockHolding = {
  player_id: number;
  player_name: string;
  quantity: number;
  current_price: number;
  market_value: number;
};

export type MockPortfolio = {
  balance: number;
  holdings: MockHolding[];
  total_value: number;
};

export type MockTransaction = {
  id: number;
  player_name: string;
  side: "BUY" | "SELL";
  quantity: number;
  status: "PENDING" | "FILLED" | "CANCELLED";
  execution_price: number | null;
  created_at: string;
};

export type MockLeaderboardEntry = {
  username: string;
  total_value: number;
  rank: number;
};

export const mockUser: MockUser = {
  id: 11,
  username: "summoner-kyle",
  balance: 4200.5,
  created_at: "2026-01-17T08:00:00Z",
};

export const mockPlayers: MockPlayer[] = [
  {
    id: 1,
    display_name: "Faker",
    game_name: "Hide on bush",
    tag_line: "KR1",
    current_price: 183.42,
    last_updated: "2026-02-22T19:30:00Z",
    lp_signal_24h: 31,
  },
  {
    id: 2,
    display_name: "Chovy",
    game_name: "DRX Chovy",
    tag_line: "KR1",
    current_price: 169.15,
    last_updated: "2026-02-22T19:30:00Z",
    lp_signal_24h: -12,
  },
  {
    id: 3,
    display_name: "Caps",
    game_name: "G2 Caps",
    tag_line: "EUW",
    current_price: 141.87,
    last_updated: "2026-02-22T19:30:00Z",
    lp_signal_24h: 7,
  },
  {
    id: 4,
    display_name: "ShowMaker",
    game_name: "DK ShowMaker",
    tag_line: "KR1",
    current_price: 132.66,
    last_updated: "2026-02-22T19:30:00Z",
    lp_signal_24h: -4,
  },
];

export const mockPortfolio: MockPortfolio = {
  balance: mockUser.balance,
  holdings: [
    {
      player_id: 1,
      player_name: "Faker",
      quantity: 8,
      current_price: 183.42,
      market_value: 1467.36,
    },
    {
      player_id: 3,
      player_name: "Caps",
      quantity: 10,
      current_price: 141.87,
      market_value: 1418.7,
    },
  ],
  total_value: 7086.56,
};

export const mockOrders: MockOrder[] = [
  {
    id: 2201,
    player_id: 2,
    player_name: "Chovy",
    side: "SELL",
    quantity: 2,
    status: "PENDING",
    execution_price: null,
    created_at: "2026-02-22T16:42:00Z",
    executed_at: null,
  },
  {
    id: 2200,
    player_id: 1,
    player_name: "Faker",
    side: "BUY",
    quantity: 3,
    status: "FILLED",
    execution_price: 179.2,
    created_at: "2026-02-21T12:11:00Z",
    executed_at: "2026-02-21T12:30:00Z",
  },
  {
    id: 2199,
    player_id: 4,
    player_name: "ShowMaker",
    side: "BUY",
    quantity: 2,
    status: "CANCELLED",
    execution_price: null,
    created_at: "2026-02-22T17:03:00Z",
    executed_at: null,
  },
];

export const mockTransactions: MockTransaction[] = [
  {
    id: 1001,
    player_name: "Faker",
    side: "BUY",
    quantity: 3,
    status: "FILLED",
    execution_price: 179.2,
    created_at: "2026-02-21T12:11:00Z",
  },
  {
    id: 1002,
    player_name: "Chovy",
    side: "SELL",
    quantity: 2,
    status: "PENDING",
    execution_price: null,
    created_at: "2026-02-22T16:42:00Z",
  },
  {
    id: 1003,
    player_name: "Caps",
    side: "BUY",
    quantity: 5,
    status: "FILLED",
    execution_price: 140.05,
    created_at: "2026-02-22T09:20:00Z",
  },
  {
    id: 1004,
    player_name: "ShowMaker",
    side: "BUY",
    quantity: 2,
    status: "CANCELLED",
    execution_price: null,
    created_at: "2026-02-22T17:03:00Z",
  },
];

export const mockLeaderboard: MockLeaderboardEntry[] = [
  {
    username: "summoner-matt",
    total_value: 8150.32,
    rank: 1,
  },
  {
    username: "summoner-kyle",
    total_value: 7086.56,
    rank: 2,
  },
  {
    username: "summoner-anne",
    total_value: 6734.11,
    rank: 3,
  },
  {
    username: "summoner-lucas",
    total_value: 5901.48,
    rank: 4,
  },
];
