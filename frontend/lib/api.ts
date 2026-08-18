import axios from 'axios'

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export interface ReceiptLineItem {
  description: string
  amount: number
}

export interface ReceiptOcr {
  raw_text: string
  merchant: string | null
  date: string | null
  subtotal: number | null
  tax: number | null
  total: number | null
  items: ReceiptLineItem[]
}

export interface TransformResult {
  /** Object URL for the corrected image (caller must revoke when done). */
  imageUrl: string
  /** Whether the backend detected a receipt boundary (vs. fallback). */
  detected: boolean
  message: string
  /** Present only when OCR was requested. */
  ocr?: ReceiptOcr
}

interface TransformJsonResponse {
  detected: boolean
  message: string
  content_type: string
  image_base64: string
  ocr?: ReceiptOcr
}

function base64ToBlob(base64: string, contentType: string): Blob {
  const binary = atob(base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: contentType })
}

/**
 * Send an image to the FastAPI backend for perspective correction.
 *
 * When ``ocr`` is false (default) the raw-bytes response is used for speed and
 * detection metadata is read from response headers. When ``ocr`` is true the
 * JSON envelope is used so extracted text/fields come back alongside the image.
 */
export async function transformReceipt(
  file: File,
  options: { ocr?: boolean } = {},
): Promise<TransformResult> {
  const formData = new FormData()
  formData.append('file', file)

  if (options.ocr) {
    const response = await axios.post<TransformJsonResponse>(
      `${API_BASE_URL}/api/receipt/transform`,
      formData,
      { params: { response_format: 'json', ocr: true } },
    )
    const data = response.data
    const blob = base64ToBlob(data.image_base64, data.content_type)
    return {
      imageUrl: URL.createObjectURL(blob),
      detected: data.detected,
      message: data.message,
      ocr: data.ocr,
    }
  }

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
