import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, del } from "./client";
import type {
  UserResponse,
  PlayerSummary,
  PlayerDetail,
  OrderResponse,
  OrderCreate,
  UserOnboardingCreate,
  PortfolioResponse,
  LeaderboardEntry,
} from "../types";

// ---- Keys ----

export const queryKeys = {
  user: ["user"] as const,
  players: ["players"] as const,
  player: (id: number) => ["player", id] as const,
  portfolio: ["portfolio"] as const,
  orders: ["orders"] as const,
  leaderboard: ["leaderboard"] as const,
};

// ---- Queries ----

export function useUser() {
  return useQuery<UserResponse>({
    queryKey: queryKeys.user,
    queryFn: () => get<UserResponse>("/user/me"),
  });
}

export function usePlayers() {
  return useQuery<PlayerSummary[]>({
    queryKey: queryKeys.players,
    queryFn: () => get<PlayerSummary[]>("/market/players"),
    refetchInterval: 30_000,
  });
}

export function usePlayer(id: number) {
  return useQuery<PlayerDetail>({
    queryKey: queryKeys.player(id),
    queryFn: () => get<PlayerDetail>(`/market/players/${id}`),
  });
}

export function usePortfolio(enabled = true) {
  return useQuery<PortfolioResponse>({
    queryKey: queryKeys.portfolio,
    queryFn: () => get<PortfolioResponse>("/portfolio"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useOrders(enabled = true) {
  return useQuery<OrderResponse[]>({
    queryKey: queryKeys.orders,
    queryFn: () => get<OrderResponse[]>("/orders"),
    enabled,
    refetchInterval: 15_000,
  });
}

export function useLeaderboard() {
  return useQuery<LeaderboardEntry[]>({
    queryKey: queryKeys.leaderboard,
    queryFn: () => get<LeaderboardEntry[]>("/leaderboard"),
    refetchInterval: 60_000,
  });
}

// ---- Mutations ----

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation<OrderResponse, Error, OrderCreate>({
    mutationFn: (body) => post<OrderResponse>("/orders", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
    },
  });
}

export function useCancelOrder() {
  const qc = useQueryClient();
  return useMutation<OrderResponse, Error, number>({
    mutationFn: (orderId) => del<OrderResponse>(`/orders/${orderId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
    },
  });
}

export function useCompleteOnboarding() {
  const qc = useQueryClient();
  return useMutation<UserResponse, Error, UserOnboardingCreate>({
    mutationFn: (body) => post<UserResponse>("/user/onboarding", body),
    onSuccess: async (user) => {
      qc.setQueryData(queryKeys.user, user);
      await qc.refetchQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.players });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.leaderboard });
    },
  });
}
