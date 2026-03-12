import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "./client";
import type {
  AdminOverviewResponse,
  AdminPlayerInsightResponse,
  AdminUserPortfolioResponse,
  AdminUserSummaryResponse,
  BalanceInsightsResponse,
  BankActionRequest,
  BankSummaryResponse,
  GambaCreate,
  GambaPositionResponse,
  OrderDetailResponse,
  UserResponse,
  PlayerSummary,
  PlayerDetail,
  OrderResponse,
  OrderCreate,
  PoroClaimRequest,
  PoroClaimResponse,
  PoroStateResponse,
  UserOnboardingCreate,
  UserProfileUpdate,
  PortfolioResponse,
  LeaderboardEntry,
  SystemStatusResponse,
} from "../types";

// ---- Keys ----

export const queryKeys = {
  user: ["user"] as const,
  players: ["players"] as const,
  player: (id: number, limit?: number | null) =>
    ["player", id, limit ?? "all"] as const,
  portfolio: ["portfolio"] as const,
  orders: ["orders"] as const,
  recentOrders: ["recentOrders"] as const,
  leaderboard: ["leaderboard"] as const,
  systemStatus: ["systemStatus"] as const,
  adminOverview: ["adminOverview"] as const,
  adminUsers: ["adminUsers"] as const,
  adminOrders: ["adminOrders"] as const,
  adminSystemStatus: ["adminSystemStatus"] as const,
  adminPlayerInsights: ["adminPlayerInsights"] as const,
  adminUserPortfolio: (userId: number) =>
    ["adminUserPortfolio", userId] as const,
  gamba: ["gamba"] as const,
  bank: ["bank"] as const,
  balanceInsights: ["balanceInsights"] as const,
  poro: ["poro"] as const,
};

const PORO_ACTIVE_POLL_MS = 5_000;
const PORO_IDLE_POLL_MS = 5_000;

function getInitialDocumentVisibility() {
  if (typeof document === "undefined") {
    return true;
  }

  return document.visibilityState === "visible";
}

function useDocumentVisible() {
  const [isVisible, setIsVisible] = useState(getInitialDocumentVisibility);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    function handleVisibilityChange() {
      setIsVisible(document.visibilityState === "visible");
    }

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  return isVisible;
}

function usePoroStreamSync(enabled: boolean) {
  const qc = useQueryClient();
  const isVisible = useDocumentVisible();
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (
      !enabled ||
      !isVisible ||
      typeof window === "undefined" ||
      typeof window.EventSource === "undefined"
    ) {
      return;
    }

    let isClosed = false;
    const stream = new window.EventSource("/api/poro/stream");

    stream.onopen = () => {
      if (!isClosed) {
        setIsConnected(true);
      }
    };

    stream.onmessage = (event) => {
      if (isClosed) {
        return;
      }

      try {
        const payload = JSON.parse(event.data) as PoroStateResponse;
        qc.setQueryData(queryKeys.poro, payload);
        setIsConnected(true);
      } catch {
        setIsConnected(false);
      }
    };

    stream.onerror = () => {
      if (!isClosed) {
        setIsConnected(false);
      }
    };

    return () => {
      isClosed = true;
      setIsConnected(false);
      stream.close();
    };
  }, [enabled, isVisible, qc]);

  return enabled && isVisible ? isConnected : false;
}

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

export function usePlayer(id: number, limit: number | null = null) {
  const search = limit === null ? "" : `?limit=${limit}`;

  return useQuery<PlayerDetail>({
    queryKey: queryKeys.player(id, limit),
    queryFn: () => get<PlayerDetail>(`/market/players/${id}${search}`),
    refetchInterval: 60_000,
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

export function useRecentOrders(enabled = true) {
  return useQuery<OrderResponse[]>({
    queryKey: queryKeys.recentOrders,
    queryFn: () => get<OrderResponse[]>("/orders/recent"),
    enabled,
    refetchInterval: 15_000,
  });
}

export function useOrderDetail(orderId: number | null, enabled = true) {
  return useQuery<OrderDetailResponse>({
    queryKey: ["orderDetail", orderId],
    queryFn: () => get<OrderDetailResponse>(`/orders/${orderId}`),
    enabled: enabled && orderId !== null,
  });
}

export function useLeaderboard() {
  return useQuery<LeaderboardEntry[]>({
    queryKey: queryKeys.leaderboard,
    queryFn: () => get<LeaderboardEntry[]>("/leaderboard"),
    refetchInterval: 60_000,
  });
}

export function useSystemStatus() {
  return useQuery<SystemStatusResponse>({
    queryKey: queryKeys.systemStatus,
    queryFn: () => get<SystemStatusResponse>("/system/status"),
    refetchInterval: 30_000,
  });
}

export function useAdminOverview(enabled = true) {
  return useQuery<AdminOverviewResponse>({
    queryKey: queryKeys.adminOverview,
    queryFn: () => get<AdminOverviewResponse>("/admin/overview"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useAdminUsers(enabled = true) {
  return useQuery<AdminUserSummaryResponse[]>({
    queryKey: queryKeys.adminUsers,
    queryFn: () => get<AdminUserSummaryResponse[]>("/admin/users"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useAdminOrders(enabled = true) {
  return useQuery<OrderResponse[]>({
    queryKey: queryKeys.adminOrders,
    queryFn: () => get<OrderResponse[]>("/admin/orders"),
    enabled,
    refetchInterval: 15_000,
  });
}

export function useAdminSystemStatus(enabled = true) {
  return useQuery<SystemStatusResponse>({
    queryKey: queryKeys.adminSystemStatus,
    queryFn: () => get<SystemStatusResponse>("/admin/system/status"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useAdminPlayerInsights(enabled = true) {
  return useQuery<AdminPlayerInsightResponse[]>({
    queryKey: queryKeys.adminPlayerInsights,
    queryFn: () => get<AdminPlayerInsightResponse[]>("/admin/players/insights"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useAdminUserPortfolio(userId: number | null, enabled = true) {
  return useQuery<AdminUserPortfolioResponse>({
    queryKey: queryKeys.adminUserPortfolio(userId ?? 0),
    queryFn: () =>
      get<AdminUserPortfolioResponse>(`/admin/users/${userId}/portfolio`),
    enabled: enabled && userId !== null,
  });
}

export function useGambaPositions(enabled = true) {
  return useQuery<GambaPositionResponse[]>({
    queryKey: queryKeys.gamba,
    queryFn: () => get<GambaPositionResponse[]>("/gamba"),
    enabled,
    refetchInterval: 15_000,
  });
}

export function useBankSummary(enabled = true) {
  return useQuery<BankSummaryResponse>({
    queryKey: queryKeys.bank,
    queryFn: () => get<BankSummaryResponse>("/bank"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function useBalanceInsights(enabled = true) {
  return useQuery<BalanceInsightsResponse>({
    queryKey: queryKeys.balanceInsights,
    queryFn: () => get<BalanceInsightsResponse>("/user/balance-insights"),
    enabled,
    refetchInterval: 30_000,
  });
}

export function usePoroState(enabled = true) {
  const isStreamConnected = usePoroStreamSync(enabled);

  return useQuery<PoroStateResponse>({
    queryKey: queryKeys.poro,
    queryFn: () => get<PoroStateResponse>("/poro"),
    enabled,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchOnReconnect: true,
    refetchInterval: (query) => {
      if (isStreamConnected) {
        return false;
      }

      const data = query.state.data;
      if (!enabled || !data?.enabled) {
        return false;
      }

      if (data.active_spawn) {
        return PORO_ACTIVE_POLL_MS;
      }

      return PORO_IDLE_POLL_MS;
    },
    refetchIntervalInBackground: true,
  });
}

// ---- Mutations ----

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation<OrderResponse, Error, OrderCreate>({
    mutationFn: (body) => post<OrderResponse>("/orders", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.recentOrders });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
    },
  });
}

export function useCancelOrder() {
  const qc = useQueryClient();
  return useMutation<OrderResponse, Error, number>({
    mutationFn: (orderId) => del<OrderResponse>(`/orders/${orderId}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.recentOrders });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
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
      void qc.invalidateQueries({ queryKey: queryKeys.recentOrders });
      void qc.invalidateQueries({ queryKey: queryKeys.leaderboard });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
    },
  });
}

export function useUpdateUserProfile() {
  const qc = useQueryClient();
  return useMutation<UserResponse, Error, UserProfileUpdate>({
    mutationFn: (body) => put<UserResponse>("/user/profile", body),
    onSuccess: async (user) => {
      qc.setQueryData(queryKeys.user, user);
      await qc.refetchQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.players });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.recentOrders });
      void qc.invalidateQueries({ queryKey: queryKeys.leaderboard });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
    },
  });
}

export function useCreateGambaPosition() {
  const qc = useQueryClient();
  return useMutation<GambaPositionResponse, Error, GambaCreate>({
    mutationFn: (body) => post<GambaPositionResponse>("/gamba", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.gamba });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.orders });
      void qc.invalidateQueries({ queryKey: queryKeys.recentOrders });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
    },
  });
}

function invalidateBankRelatedQueries(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: queryKeys.bank });
  void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
  void qc.invalidateQueries({ queryKey: queryKeys.user });
  void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
  void qc.invalidateQueries({ queryKey: queryKeys.leaderboard });
}

export function useBorrowFromBank() {
  const qc = useQueryClient();
  return useMutation<BankSummaryResponse, Error, BankActionRequest>({
    mutationFn: (body) => post<BankSummaryResponse>("/bank/borrow", body),
    onSuccess: () => {
      invalidateBankRelatedQueries(qc);
    },
  });
}

export function useRepayBankDebt() {
  const qc = useQueryClient();
  return useMutation<BankSummaryResponse, Error, BankActionRequest>({
    mutationFn: (body) => post<BankSummaryResponse>("/bank/repay", body),
    onSuccess: () => {
      invalidateBankRelatedQueries(qc);
    },
  });
}

export function useRestoreAdminRescue(userId: number | null) {
  const qc = useQueryClient();
  return useMutation<AdminUserPortfolioResponse, Error, void>({
    mutationFn: () =>
      post<AdminUserPortfolioResponse>(
        `/admin/users/${userId}/rescue-unlock`,
        {},
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.adminUsers });
      void qc.invalidateQueries({ queryKey: queryKeys.adminOverview });
      if (userId !== null) {
        void qc.invalidateQueries({
          queryKey: queryKeys.adminUserPortfolio(userId),
        });
      }
    },
  });
}

export function useClaimPoro() {
  const qc = useQueryClient();
  return useMutation<PoroClaimResponse, Error, PoroClaimRequest>({
    mutationFn: (body) => post<PoroClaimResponse>("/poro/claim", body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: queryKeys.poro });
      void qc.invalidateQueries({ queryKey: queryKeys.user });
      void qc.invalidateQueries({ queryKey: queryKeys.balanceInsights });
      void qc.invalidateQueries({ queryKey: queryKeys.portfolio });
      void qc.invalidateQueries({ queryKey: queryKeys.bank });
      void qc.invalidateQueries({ queryKey: queryKeys.leaderboard });
    },
  });
}
