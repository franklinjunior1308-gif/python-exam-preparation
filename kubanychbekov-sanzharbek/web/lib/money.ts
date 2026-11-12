/**
 * Money is whole tyiyn (1 KGS = 100 tyiyn). Nothing here uses floating-point for amounts, so what the
 * user types, what the preview shows and what the server stores agree to the last tyiyn (DATA-04).
 */

/** 123456 -> "1 234.56 KGS". */
export function formatKgs(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  const whole = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const fraction = String(abs % 100).padStart(2, "0");
  return `${sign}${whole}.${fraction} KGS`;
}

/** "120.50" or "120,5" -> 12050; null for anything that is not a non-negative amount with <= 2 decimals. */
export function parseKgsToCents(input: string): number | null {
  const text = input.trim().replace(",", ".");
  const match = /^(\d{1,10})(?:\.(\d{1,2}))?$/.exec(text);
  if (!match) return null;
  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(2, "0"));
  return whole * 100 + fraction;
}

/** "2" or "0.5" -> 500 (thousandths); null unless it is a positive quantity with <= 3 decimals. */
export function parseQuantityMilli(input: string): number | null {
  const match = /^(\d{1,9})(?:[.,](\d{1,3}))?$/.exec(input.trim());
  if (!match) return null;
  const milli = Number(match[1]) * 1000 + Number((match[2] ?? "").padEnd(3, "0"));
  return milli > 0 ? milli : null;
}

/** quantity x unit price in whole tyiyn, rounded half-up (same rule as the backend). */
export function lineTotalCents(quantityMilli: number, unitPriceCents: number): number {
  return Math.floor((quantityMilli * unitPriceCents + 500) / 1000);
}

/** minutes at an hourly rate in whole tyiyn, rounded half-up (same rule as the backend). */
export function laborTotalCents(minutes: number, ratePerHourCents: number): number {
  return Math.floor((minutes * ratePerHourCents + 30) / 60);
}

/** "2.000" (as sent by the API) -> "2"; "0.500" -> "0.5". */
export function trimQuantity(quantity: string): string {
  return quantity.includes(".") ? quantity.replace(/0+$/, "").replace(/\.$/, "") : quantity;
}

/** Working minutes -> "2 h 30 min" (units are passed in so the caller can translate them). */
export function formatDuration(totalMinutes: number, hourUnit: string, minuteUnit: string): string {
  const abs = Math.abs(Math.round(totalMinutes));
  const hours = Math.floor(abs / 60);
  const minutes = abs % 60;
  if (hours === 0) return `${minutes} ${minuteUnit}`;
  return minutes === 0 ? `${hours} ${hourUnit}` : `${hours} ${hourUnit} ${minutes} ${minuteUnit}`;
}
