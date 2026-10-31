/** Formats a latest value: fractional numbers get `precision` decimals, others show as-is. */
export function formatValue(value: string, precision: number): string {
  const trimmed = value.trim();
  const number = Number(trimmed);
  if (trimmed === "" || !Number.isFinite(number) || Number.isInteger(number)) return value;
  return number.toFixed(precision);
}

/** Formats a cursor position in seconds; null means the host follows live data. */
export function formatCursor(cursorS: number | null): string {
  return cursorS === null ? "Live" : `${cursorS.toFixed(3)} s`;
}
