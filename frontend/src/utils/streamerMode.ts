export function getStreamerSafeName(
  gameName?: string | null,
  fallbackName?: string | null,
): string {
  const trimmedGameName = gameName?.trim();
  if (trimmedGameName) {
    return trimmedGameName;
  }

  return fallbackName?.trim() ?? "";
}
