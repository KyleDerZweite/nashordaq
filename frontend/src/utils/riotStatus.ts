import type { SystemStatusResponse } from "../types";

const unavailableStatuses: readonly SystemStatusResponse["riot_status"][] = [
  "missing_key",
  "invalid_key",
  "unavailable",
  "rate_limited",
];

export function isRiotUnavailable(status: SystemStatusResponse["riot_status"]) {
  return unavailableStatuses.includes(status);
}
