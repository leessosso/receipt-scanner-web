import axios from 'axios'

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export interface TransformResult {
  /** Object URL for the corrected image (caller must revoke when done). */
  imageUrl: string
  /** Whether the backend detected a receipt boundary (vs. fallback). */
  detected: boolean
  message: string
}

/**
 * Send an image to the FastAPI backend for perspective correction.
 *
 * Uses the raw-bytes response (`response_format=image`) and reads detection
 * metadata from response headers, keeping the door open for a future OCR
 * response envelope without changing this call site.
 */
export async function transformReceipt(file: File): Promise<TransformResult> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await axios.post(
    `${API_BASE_URL}/api/receipt/transform`,
    formData,
    {
      responseType: 'blob',
      params: { response_format: 'image' },
    },
  )

  const detected = response.headers['x-receipt-detected'] === 'true'
  const message =
    (response.headers['x-receipt-message'] as string | undefined) ?? ''
  const imageUrl = URL.createObjectURL(response.data as Blob)

  return { imageUrl, detected, message }
}
