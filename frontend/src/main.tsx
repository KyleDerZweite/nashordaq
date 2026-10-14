import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import AuthGate from "./components/AuthGate";
import { ApiError } from "./api/client";
import { StreamerModeProvider } from "./contexts/StreamerModeContext";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status === 401) &&
        failureCount < 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <StreamerModeProvider>
        <AuthGate />
      </StreamerModeProvider>
    </QueryClientProvider>
  </StrictMode>,
);
