import { describe, expect, it } from 'vitest'
import { formatCurrency } from './format'

describe('formatCurrency', () => {
  it('formats USD with two decimals', () => {
    expect(formatCurrency(24.36, 'USD')).toBe('$24.36')
    expect(formatCurrency(1234.5, 'USD')).toBe('$1,234.50')
  })

  it('formats KRW as won with no decimals', () => {
    expect(formatCurrency(6300, 'KRW')).toBe('₩6,300')
    expect(formatCurrency(18400, 'KRW')).toBe('₩18,400')
  })

  it('formats unknown currency as a grouped number', () => {
    expect(formatCurrency(6300)).toBe('6,300')
    expect(formatCurrency(24.36, null)).toBe('24.36')
  })

  it('returns an em dash for null/undefined', () => {
    expect(formatCurrency(null, 'USD')).toBe('—')
    expect(formatCurrency(undefined)).toBe('—')
  })
})
