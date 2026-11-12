/**
 * Time helpers for an organization that lives in one IANA timezone.
 *
 * The backend stores UTC. People type and read wall-clock time in the organization's zone,
 * never in the browser's zone, so every conversion here is explicit about the zone.
 */

type Parts = { year: number; month: number; day: number; hour: number; minute: number; second: number };

function zonedParts(timestamp: number, timeZone: string): Parts {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const get = (type: string) =>
    Number(formatter.formatToParts(new Date(timestamp)).find((p) => p.type === type)?.value);
  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
    second: get("second"),
  };
}

/** Offset of `timeZone` from UTC at an instant, in milliseconds. */
function offsetAt(timestamp: number, timeZone: string): number {
  const p = zonedParts(timestamp, timeZone);
  const asIfUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return asIfUtc - Math.floor(timestamp / 1000) * 1000;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** "2026-11-16T10:00" typed in the organization's zone -> UTC ISO string. */
export function zonedInputToIso(value: string, timeZone: string): string {
  const [date = "", time = "00:00"] = value.split("T");
  const [y = 1970, m = 1, d = 1] = date.split("-").map(Number);
  const [hh = 0, mm = 0] = time.split(":").map(Number);
  const wall = Date.UTC(y, m - 1, d, hh, mm);
  let ts = wall - offsetAt(wall, timeZone);
  const corrected = wall - offsetAt(ts, timeZone); // handles offsets that change around that day
  if (corrected !== ts) ts = corrected;
  return new Date(ts).toISOString();
}

/** UTC ISO string -> "YYYY-MM-DDTHH:mm" in the organization's zone (for <input type=datetime-local>). */
export function isoToZonedInput(iso: string, timeZone: string): string {
  const p = zonedParts(new Date(iso).getTime(), timeZone);
  return `${p.year}-${pad(p.month)}-${pad(p.day)}T${pad(p.hour)}:${pad(p.minute)}`;
}

/** Calendar date ("YYYY-MM-DD") and minutes after local midnight of an instant. */
export function localParts(iso: string, timeZone: string): { date: string; minutes: number } {
  const p = zonedParts(new Date(iso).getTime(), timeZone);
  return { date: `${p.year}-${pad(p.month)}-${pad(p.day)}`, minutes: p.hour * 60 + p.minute };
}

export function todayInZone(timeZone: string): string {
  return localParts(new Date().toISOString(), timeZone).date;
}

export function addDays(date: string, days: number): string {
  const [y = 1970, m = 1, d = 1] = date.split("-").map(Number);
  const moved = new Date(Date.UTC(y, m - 1, d + days));
  return `${moved.getUTCFullYear()}-${pad(moved.getUTCMonth() + 1)}-${pad(moved.getUTCDate())}`;
}

/** Monday of the week containing `date` (weeks start on Monday). */
export function weekStart(date: string): string {
  const [y = 1970, m = 1, d = 1] = date.split("-").map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7; // 0 = Monday
  return addDays(date, -weekday);
}

/** [from, to) of `days` calendar days starting at `date`, as UTC ISO strings. */
export function rangeIso(date: string, days: number, timeZone: string): { from: string; to: string } {
  return {
    from: zonedInputToIso(`${date}T00:00`, timeZone),
    to: zonedInputToIso(`${addDays(date, days)}T00:00`, timeZone),
  };
}

/** Monday = 0 ... Sunday = 6 for a calendar date. */
export function weekdayOf(date: string): number {
  const [y = 1970, m = 1, d = 1] = date.split("-").map(Number);
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7;
}

export function formatClock(iso: string, timeZone: string): string {
  const { minutes } = localParts(iso, timeZone);
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`;
}
