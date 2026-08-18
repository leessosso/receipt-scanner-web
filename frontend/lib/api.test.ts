import { describe, expect, it } from 'vitest'
import { base64ToBlob } from './api'

describe('base64ToBlob', () => {
  it('decodes base64 into a Blob with the given content type', async () => {
    const original = 'hello world'
    const base64 = Buffer.from(original).toString('base64')

    const blob = base64ToBlob(base64, 'image/jpeg')

    expect(blob.type).toBe('image/jpeg')
    expect(blob.size).toBe(original.length)
    expect(await blob.text()).toBe(original)
  })
})
