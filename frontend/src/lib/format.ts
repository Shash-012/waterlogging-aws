// Contract times are UTC with Z; the UI shows IST.
const IST_TIME = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})
const IST_DATE_TIME = new Intl.DateTimeFormat('en-IN', {
  timeZone: 'Asia/Kolkata',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})
const IST_DATE = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kolkata',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

export const formatIstTime = (iso: string) => `${IST_TIME.format(new Date(iso))} IST`
export const formatIstDateTime = (iso: string) => `${IST_DATE_TIME.format(new Date(iso))} IST`
export const formatIstDate = (iso: string) => IST_DATE.format(new Date(iso))

const HOUR_MS = 3_600_000

export function hoursBetween(fromIso: string, toIso: string): number {
  return (Date.parse(toIso) - Date.parse(fromIso)) / HOUR_MS
}

export function addHours(iso: string, hours: number): string {
  return new Date(Date.parse(iso) + hours * HOUR_MS).toISOString().replace('.000Z', 'Z')
}

// Peak time relative to the snapshot it came from, e.g. "in 3 h".
export function relativePeak(peakAt: string | null, asOf: string): string {
  if (!peakAt) return 'no rain forecast'
  const h = Math.round(hoursBetween(asOf, peakAt))
  if (h <= 0) return 'now'
  return `in ${h} h`
}

export const formatScore = (x: number) => x.toFixed(2)
