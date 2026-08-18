/**
 * Format a nullable amount for display, honoring the detected currency.
 *
 * - `KRW` → won with no decimals (₩6,300)
 * - `USD` → dollars with two decimals ($24.36)
 * - unknown → grouped number with no currency symbol
 */
export function formatCurrency(
  value: number | null | undefined,
  currency?: string | null,
): string {
  if (value === null || value === undefined) return '—'

  if (currency === 'KRW') {
    return new Intl.NumberFormat('ko-KR', {
      style: 'currency',
      currency: 'KRW',
      maximumFractionDigits: 0,
    }).format(value)
  }

  if (currency === 'USD') {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value)
  }

  return new Intl.NumberFormat('en-US').format(value)
}
