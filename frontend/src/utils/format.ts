export function formatAmount(value: number): string {
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatQuantity(value: number): string {
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
    maximumFractionDigits: 4,
  });
}

const BACKEND_UTC_OFFSET_PATTERN = /(?:Z|[+-]\d{2}:\d{2})$/i;

export function parseBackendUtcTimestamp(value: string): Date {
  return new Date(BACKEND_UTC_OFFSET_PATTERN.test(value) ? value : `${value}Z`);
}

export function formatLocalTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseBackendUtcTimestamp(value));
}

export function formatLocalDate(value: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parseBackendUtcTimestamp(value));
}

export function formatLocalDateShort(value: string): string {
  return new Intl.DateTimeFormat("de-DE", {
    day: "2-digit",
    month: "short",
  }).format(parseBackendUtcTimestamp(value));
}

export function formatLocalDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parseBackendUtcTimestamp(value));
}
