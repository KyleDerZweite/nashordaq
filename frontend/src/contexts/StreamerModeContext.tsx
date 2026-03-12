import { useEffect, useMemo, useState } from "react";

import {
  readInitialStreamerMode,
  STREAMER_MODE_STORAGE_KEY,
  StreamerModeContext,
} from "./streamerModeContext";

export function StreamerModeProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isStreamerMode, setIsStreamerMode] = useState(readInitialStreamerMode);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      STREAMER_MODE_STORAGE_KEY,
      isStreamerMode ? "true" : "false",
    );
  }, [isStreamerMode]);

  const value = useMemo(
    () => ({
      isStreamerMode,
      setStreamerMode: setIsStreamerMode,
      toggleStreamerMode: () => setIsStreamerMode((current) => !current),
    }),
    [isStreamerMode],
  );

  return (
    <StreamerModeContext.Provider value={value}>
      {children}
    </StreamerModeContext.Provider>
  );
}
