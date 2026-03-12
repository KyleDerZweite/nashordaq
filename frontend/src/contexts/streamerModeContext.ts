import { createContext } from "react";

export const STREAMER_MODE_STORAGE_KEY = "nashordaq.streamer-mode";

export interface StreamerModeContextValue {
  isStreamerMode: boolean;
  setStreamerMode: (value: boolean) => void;
  toggleStreamerMode: () => void;
}

export const StreamerModeContext = createContext<
  StreamerModeContextValue | undefined
>(undefined);

export function readInitialStreamerMode(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return window.localStorage.getItem(STREAMER_MODE_STORAGE_KEY) === "true";
}
