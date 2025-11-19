// src/views/pages/UploadPage.tsx
import React, { useState } from 'react'
import { API_BASE } from '../../config'

export const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null)
  const [cameraId, setCameraId] = useState('camera-01')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<any | null>(null)

  const handleUpload = async () => {
    if (!file) {
      setError('Please select an image file.')
      return
    }
    setError(null)
    setLoading(true)
    setResponse(null)

    try {
      const form = new FormData()
      form.append('file', file)
      form.append('camera_id', cameraId || 'camera-01')

      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: form,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data?.detail || `Upload failed (${res.status})`)
      }
      const fullUrl = data.url ? `${API_BASE}${data.url}` : null
      setResponse({ ...data, fullUrl })
    } catch (e: any) {
      setError(e?.message || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-full flex-col bg-slate-50/60">
      <div className="flex flex-1 flex-col gap-4 overflow-auto p-6 lg:flex-row">
        {/* Left: form card */}
        <div className="w-full rounded-xl bg-white p-5 shadow-sm ring-1 ring-slate-100 lg:w-80">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            New Capture
          </h2>
          <p className="mt-1 text-[11px] text-slate-500">
            Select a camera and upload a still image to send it through the VLM
            pipeline.
          </p>

          <div className="mt-4 space-y-3 text-sm">
            <div>
              <label className="block text-xs font-medium text-slate-700">
                Camera ID
              </label>
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-900 focus:border-slate-900 focus:outline-none"
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                placeholder="camera-01"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700">
                Image File
              </label>
              <div className="mt-1 flex items-center justify-between gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-2">
                <input
                  type="file"
                  accept="image/*"
                  className="block w-full text-[11px] text-slate-700"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 px-3 py-2 text-[11px] text-red-700">
                {error}
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={loading}
              className="mt-2 w-full rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? 'Uploading…' : 'Upload & Analyze'}
            </button>

            <div className="pt-2 text-[10px] text-slate-400">
              POST <span className="font-mono text-[10px]">{API_BASE}/upload</span>
            </div>
          </div>
        </div>

        {/* Right: response + preview */}
        <div className="flex-1 space-y-4">
          <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Backend Response
            </h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Includes ID, match distance, and change detection flags.
            </p>

            {!response && !loading && (
              <p className="mt-3 text-[11px] text-slate-400">
                No upload yet. Submit an image to see structured response.
              </p>
            )}
            {loading && (
              <p className="mt-3 text-[11px] text-slate-500">Waiting for response…</p>
            )}
            {response && (
              <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-[11px] text-slate-800">
                {JSON.stringify(response, null, 2)}
              </pre>
            )}
          </div>

          {response?.fullUrl && (
            <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Uploaded Image
              </h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Raw frame as ingested by the pipeline.
              </p>
              <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                {/* eslint-disable-next-line jsx-a11y/alt-text */}
                <img
                  src={response.fullUrl}
                  className="max-h-80 w-full object-contain"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
