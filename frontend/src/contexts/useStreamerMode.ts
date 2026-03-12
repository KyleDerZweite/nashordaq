import { useContext } from "react";

import { StreamerModeContext } from "./streamerModeContext";

export function useStreamerMode() {
  const context = useContext(StreamerModeContext);

  if (!context) {
    throw new Error(
      "useStreamerMode must be used within a StreamerModeProvider",
    );
  }

  return context;
}
