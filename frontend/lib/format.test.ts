import { describe, expect, it } from 'vitest'
import { formatCurrency } from './format'

describe('formatCurrency', () => {
  it('formats numbers as USD', () => {
    expect(formatCurrency(24.36)).toBe('$24.36')
    expect(formatCurrency(0)).toBe('$0.00')
    expect(formatCurrency(1234.5)).toBe('$1,234.50')
  })

  it('returns an em dash for null/undefined', () => {
    expect(formatCurrency(null)).toBe('—')
    expect(formatCurrency(undefined)).toBe('—')
  })
})
