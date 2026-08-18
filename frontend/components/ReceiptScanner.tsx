'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ImageUp,
  Loader2,
  ScanLine,
} from 'lucide-react'
import axios from 'axios'
import { saveReceipt } from '@/lib/api'

type Phase = 'idle' | 'ready' | 'saving' | 'saved' | 'error'

function todayIso(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (err.response?.status === 503) {
      return '구글 시트/드라이브가 아직 설정되지 않았습니다.'
    }
    if (err.response) return '저장에 실패했습니다. 잠시 후 다시 시도하세요.'
    return '백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.'
  }
  return '저장에 실패했습니다. 잠시 후 다시 시도하세요.'
}

export default function ReceiptScanner() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [date, setDate] = useState(todayIso)
  const [amount, setAmount] = useState('')
  const [memo, setMemo] = useState('')
  const [error, setError] = useState('')
  const [savedUrl, setSavedUrl] = useState<string | null>(null)

  const selectedFile = useRef<File | null>(null)
  const galleryInput = useRef<HTMLInputElement>(null)
  const cameraInput = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  const handleFile = useCallback((file: File) => {
    selectedFile.current = file
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
    setError('')
    setSavedUrl(null)
    setPhase('ready')
  }, [])

  const resetForNext = useCallback(() => {
    selectedFile.current = null
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    setAmount('')
    setMemo('')
    setDate(todayIso())
    setError('')
    setPhase('idle')
  }, [])

  const handleSave = useCallback(async () => {
    if (!selectedFile.current) return
    if (!date || !amount.trim()) {
      setError('일자와 금액을 입력하세요.')
      setPhase('error')
      return
    }
    setPhase('saving')
    setError('')
    try {
      const result = await saveReceipt({
        file: selectedFile.current,
        date,
        amount,
        memo,
      })
      setSavedUrl(result.file_url)
      setPhase('saved')
    } catch (err) {
      setError(errorMessage(err))
      setPhase('error')
    }
  }, [amount, date, memo])

  const busy = phase === 'saving'
  const canSave = Boolean(previewUrl) && !busy

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-16">
      <header className="flex flex-col items-center py-8 text-center">
        <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500 text-white shadow-lg shadow-brand-500/30">
          <ScanLine className="h-8 w-8" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          영수증 정리
        </h1>
        <p className="mt-2 max-w-md text-sm text-slate-500">
          사진을 올리며 일자·금액·메모를 바로 적으면 구글 시트와 드라이브에
          저장됩니다.
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
          <p className="text-sm">이미지를 선택하면 미리보기와 입력란이 나옵니다.</p>
        </div>
      )}

      {previewUrl && (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <figure className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
            <figcaption className="border-b border-slate-100 px-4 py-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
              영수증 사진
            </figcaption>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={previewUrl}
              alt="업로드한 영수증"
              className="max-h-[420px] w-full bg-slate-50 object-contain"
            />
          </figure>

          <form
            className="flex flex-col gap-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200"
            onSubmit={(e) => {
              e.preventDefault()
              void handleSave()
            }}
          >
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">일자</span>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                disabled={busy}
                required
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-800 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">금액</span>
              <input
                type="text"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                disabled={busy}
                required
                placeholder="예: 6300"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-800 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
              />
            </label>
            <label className="block flex-1 text-sm">
              <span className="mb-1 block font-medium text-slate-700">메모</span>
              <textarea
                value={memo}
                onChange={(e) => setMemo(e.target.value)}
                disabled={busy}
                rows={4}
                placeholder="거래처, 계정과목, 적요 등"
                className="w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-slate-800 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
              />
            </label>
            <button
              type="submit"
              disabled={!canSave}
              className="mt-auto flex w-full items-center justify-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-base font-semibold text-white shadow-lg shadow-brand-600/30 transition hover:bg-brand-700 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> 저장 중…
                </>
              ) : (
                '시트에 저장'
              )}
            </button>
          </form>
        </div>
      )}

      {phase === 'saved' && savedUrl && (
        <div className="mt-4 flex flex-col gap-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800 ring-1 ring-emerald-200 sm:flex-row sm:items-center sm:justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            저장했습니다. 시트에서 내용과 사진을 확인할 수 있습니다.
          </span>
          <div className="flex gap-2">
            <a
              href={savedUrl}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg px-3 py-1.5 font-semibold text-emerald-800 hover:bg-emerald-100"
            >
              사진 열기
            </a>
            <button
              type="button"
              onClick={resetForNext}
              className="rounded-lg bg-emerald-700 px-3 py-1.5 font-semibold text-white hover:bg-emerald-800"
            >
              다음 장
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
