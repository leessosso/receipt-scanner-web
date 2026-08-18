'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  Download,
  ImageUp,
  Loader2,
  Receipt,
  RotateCw,
  ScanLine,
  Wand2,
} from 'lucide-react'
import { transformReceipt, type ReceiptOcr } from '@/lib/api'

type Phase = 'idle' | 'ready' | 'processing' | 'done' | 'error'

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(value)
}

export default function ReceiptScanner() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [originalUrl, setOriginalUrl] = useState<string | null>(null)
  const [resultUrl, setResultUrl] = useState<string | null>(null)
  const [detected, setDetected] = useState<boolean | null>(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [rotation, setRotation] = useState(0)
  const [ocrEnabled, setOcrEnabled] = useState(false)
  const [ocr, setOcr] = useState<ReceiptOcr | null>(null)

  const selectedFile = useRef<File | null>(null)
  const galleryInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)

  // Revoke object URLs on change/unmount to avoid leaks.
  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl)
    }
  }, [originalUrl])
  useEffect(() => {
    return () => {
      if (resultUrl) URL.revokeObjectURL(resultUrl)
    }
  }, [resultUrl])

  const resetResult = useCallback(() => {
    setResultUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setDetected(null)
    setMessage('')
    setRotation(0)
    setOcr(null)
  }, [])

  const handleFile = useCallback(
    (file: File) => {
      selectedFile.current = file
      setOriginalUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return URL.createObjectURL(file)
      })
      resetResult()
      setError('')
      setPhase('ready')
    },
    [resetResult],
  )

  const handleTransform = useCallback(async () => {
    if (!selectedFile.current) return
    setPhase('processing')
    setError('')
    try {
      const result = await transformReceipt(selectedFile.current, {
        ocr: ocrEnabled,
      })
      setResultUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev)
        return result.imageUrl
      })
      setDetected(result.detected)
      setMessage(result.message)
      setOcr(result.ocr ?? null)
      setRotation(0)
      setPhase('done')
    } catch (err) {
      const detail =
        (err as { response?: { data?: unknown } })?.response !== undefined
          ? '서버가 이미지를 처리하지 못했습니다.'
          : '백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.'
      setError(detail)
      setPhase('error')
    }
  }, [ocrEnabled])

  const handleDownload = useCallback(async () => {
    if (!resultUrl) return
    // Bake the current rotation into the downloaded JPEG.
    const img = new Image()
    img.src = resultUrl
    await img.decode()

    const rotated = rotation % 360
    const swap = rotated === 90 || rotated === 270
    const canvas = document.createElement('canvas')
    canvas.width = swap ? img.height : img.width
    canvas.height = swap ? img.width : img.height
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.translate(canvas.width / 2, canvas.height / 2)
    ctx.rotate((rotated * Math.PI) / 180)
    ctx.drawImage(img, -img.width / 2, -img.height / 2)

    const link = document.createElement('a')
    link.href = canvas.toDataURL('image/jpeg', 0.92)
    link.download = 'receipt-corrected.jpg'
    link.click()
  }, [resultUrl, rotation])

  const busy = phase === 'processing'

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-16">
      <header className="flex flex-col items-center py-8 text-center">
        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500 text-white shadow-lg shadow-brand-500/30">
          <ScanLine className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          영수증 원근 보정 스캐너
        </h1>
        <p className="mt-2 max-w-md text-sm text-slate-500">
          비스듬히 찍은 영수증 사진을 올리면 똑바른 직사각형으로 펴 드립니다.
        </p>
      </header>

      <div className="grid grid-cols-2 gap-3">
        <button
          type="button"
          onClick={() => cameraInput.current?.click()}
          disabled={busy}
          className="flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:bg-slate-50 active:scale-[0.98] disabled:opacity-50"
        >
          <Camera className="h-5 w-5 text-brand-600" />
          카메라 촬영
        </button>
        <button
          type="button"
          onClick={() => galleryInput.current?.click()}
          disabled={busy}
          className="flex items-center justify-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:bg-slate-50 active:scale-[0.98] disabled:opacity-50"
        >
          <ImageUp className="h-5 w-5 text-brand-600" />
          갤러리 업로드
        </button>
      </div>

      <label className="mt-3 flex cursor-pointer items-center justify-between rounded-xl bg-white px-4 py-3 text-sm shadow-sm ring-1 ring-slate-200">
        <span className="flex items-center gap-2 font-medium text-slate-700">
          <Receipt className="h-5 w-5 text-brand-600" />
          텍스트도 추출 (OCR)
        </span>
        <input
          type="checkbox"
          checked={ocrEnabled}
          onChange={(e) => setOcrEnabled(e.target.checked)}
          disabled={busy}
          className="h-5 w-5 accent-brand-600"
        />
      </label>

      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />
      <input
        ref={galleryInput}
        type="file"
        accept="image/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
          e.target.value = ''
        }}
      />

      {phase === 'idle' && (
        <div className="mt-8 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-white/60 py-16 text-slate-400">
          <ScanLine className="mb-3 h-10 w-10" />
          <p className="text-sm">이미지를 선택하면 여기에 미리보기가 표시됩니다.</p>
        </div>
      )}

      {originalUrl && (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <figure className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <figcaption className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              원본
            </figcaption>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={originalUrl}
              alt="업로드한 원본 영수증"
              className="max-h-[420px] w-full bg-slate-50 object-contain"
            />
          </figure>

          <figure className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <figcaption className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              보정 결과
              {resultUrl && (
                <span className="flex items-center gap-2 text-[11px] normal-case">
                  <button
                    type="button"
                    onClick={() => setRotation((r) => (r + 90) % 360)}
                    className="flex items-center gap-1 rounded-md px-2 py-1 font-semibold text-slate-600 hover:bg-slate-100"
                  >
                    <RotateCw className="h-3.5 w-3.5" /> 회전
                  </button>
                  <button
                    type="button"
                    onClick={handleDownload}
                    className="flex items-center gap-1 rounded-md px-2 py-1 font-semibold text-brand-600 hover:bg-brand-50"
                  >
                    <Download className="h-3.5 w-3.5" /> 저장
                  </button>
                </span>
              )}
            </figcaption>
            <div className="flex min-h-[200px] items-center justify-center bg-slate-50">
              {busy ? (
                <div className="flex flex-col items-center gap-3 py-16 text-brand-600">
                  <Loader2 className="h-8 w-8 animate-spin" />
                  <span className="text-sm font-medium">보정 처리 중…</span>
                </div>
              ) : resultUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={resultUrl}
                  alt="원근 보정된 영수증"
                  style={{ transform: `rotate(${rotation}deg)` }}
                  className="max-h-[420px] w-full object-contain transition-transform duration-300"
                />
              ) : (
                <p className="px-6 py-16 text-center text-sm text-slate-400">
                  ‘보정하기’를 누르면 결과가 여기에 표시됩니다.
                </p>
              )}
            </div>
          </figure>
        </div>
      )}

      {detected !== null && !busy && (
        <div
          className={`mt-4 flex items-center gap-2 rounded-xl px-4 py-3 text-sm ${
            detected
              ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
              : 'bg-amber-50 text-amber-700 ring-1 ring-amber-200'
          }`}
        >
          {detected ? (
            <CheckCircle2 className="h-5 w-5 shrink-0" />
          ) : (
            <AlertTriangle className="h-5 w-5 shrink-0" />
          )}
          <span>
            {detected
              ? '영수증 영역을 검출하여 평면화했습니다.'
              : '영수증 경계를 찾지 못해 보정 없이 원본을 반환했습니다.'}
          </span>
        </div>
      )}

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {ocr && !busy && (
        <div className="mt-4 overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
          <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-700">
            <Receipt className="h-5 w-5 text-brand-600" />
            추출된 텍스트
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-4 py-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">가맹점</p>
              <p className="font-medium text-slate-800">{ocr.merchant ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">날짜</p>
              <p className="font-medium text-slate-800">{ocr.date ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">합계</p>
              <p className="font-semibold text-brand-700">
                {formatCurrency(ocr.total)}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">소계</p>
              <p className="font-medium text-slate-800">
                {formatCurrency(ocr.subtotal)}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-400">세금</p>
              <p className="font-medium text-slate-800">
                {formatCurrency(ocr.tax)}
              </p>
            </div>
          </div>

          {ocr.items.length > 0 && (
            <table className="w-full border-t border-slate-100 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-400">
                  <th className="px-4 py-2 font-medium">항목</th>
                  <th className="px-4 py-2 text-right font-medium">금액</th>
                </tr>
              </thead>
              <tbody>
                {ocr.items.map((item, index) => (
                  <tr
                    key={`${item.description}-${index}`}
                    className="border-t border-slate-50"
                  >
                    <td className="px-4 py-2 text-slate-700">{item.description}</td>
                    <td className="px-4 py-2 text-right font-medium text-slate-800">
                      {formatCurrency(item.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <details className="border-t border-slate-100 px-4 py-3 text-sm">
            <summary className="cursor-pointer font-medium text-slate-600">
              원본 OCR 텍스트
            </summary>
            <pre className="mt-2 whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
              {ocr.raw_text.trim() || '(추출된 텍스트가 없습니다)'}
            </pre>
          </details>
        </div>
      )}

      {originalUrl && (
        <button
          type="button"
          onClick={handleTransform}
          disabled={busy}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-6 py-4 text-base font-semibold text-white shadow-lg shadow-brand-600/30 transition hover:bg-brand-700 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? (
            <>
              <Loader2 className="h-5 w-5 animate-spin" /> 처리 중…
            </>
          ) : (
            <>
              <Wand2 className="h-5 w-5" /> 보정하기
            </>
          )}
        </button>
      )}
    </div>
  )
}
