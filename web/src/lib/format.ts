/** Short relative time ("3 days ago"), with the absolute date kept for tooltips. */
export function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.round((Date.now() - then) / 1000);

  if (seconds < 60) return 'just now';
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ['minute', 60],
    ['hour', 3600],
    ['day', 86400],
    ['month', 2592000],
    ['year', 31536000],
  ];

  let chosen: Intl.RelativeTimeFormatUnit = 'minute';
  let divisor = 60;
  for (const [unit, unitSeconds] of units) {
    if (seconds >= unitSeconds) {
      chosen = unit;
      divisor = unitSeconds;
    }
  }
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  return formatter.format(-Math.floor(seconds / divisor), chosen);
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
