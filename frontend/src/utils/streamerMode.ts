export function obfuscateName(value: string): string {
  const trimmedValue = value.trim();

  if (trimmedValue.length === 0) {
    return trimmedValue;
  }

  const visibleCount =
    trimmedValue.length <= 2
      ? 1
      : Math.max(2, Math.floor(trimmedValue.length / 2));
  const replacedCharacterCount = Math.max(
    1,
    trimmedValue.length - visibleCount,
  );
  const maskedCount = Math.max(6 - visibleCount, replacedCharacterCount + 1);

  return `${trimmedValue.slice(0, visibleCount)}${"*".repeat(maskedCount)}`;
}

export function obfuscateRiotHandle(gameName: string, tagLine: string): string {
  return `${obfuscateName(gameName)}#${obfuscateName(tagLine)}`;
}
