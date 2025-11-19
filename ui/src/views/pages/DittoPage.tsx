import React, { useState } from 'react'
import { API_BASE } from '../../config'

export const DittoPage: React.FC = () => {
  const [cameraId, setCameraId] = useState('camera-01')
  const [imageId, setImageId] = useState('1') // DB image id
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [stateResp, setStateResp] = useState<any | null>(null)
  const [capturesResp, setCapturesResp] = useState<any | null>(null)
  const [revisionsResp, setRevisionsResp] = useState<any | null>(null)

  const handleLoad = async () => {
    const trimmedCamera = cameraId.trim()
    const trimmedImage = imageId.trim()

    if (!trimmedCamera) {
      setError('Enter camera_id')
      return
    }
    const idNum = Number(trimmedImage)
    if (!trimmedImage || Number.isNaN(idNum) || idNum <= 0) {
      setError('Enter a valid numeric image_id (DB id)')
      return
    }

    setError(null)
    setLoading(true)
    setStateResp(null)
    setCapturesResp(null)
    setRevisionsResp(null)

    try {
      const base = `${API_BASE}/ditto/image/${encodeURIComponent(
        trimmedCamera,
      )}/${idNum}`

      const [stateRes, capRes, revRes] = await Promise.all([
        fetch(base),
        fetch(`${base}/captures`),
        fetch(`${base}/revisions`),
      ])

      const stateJson = await stateRes.json()
      const capJson = await capRes.json()
      const revJson = await revRes.json()

      if (!stateRes.ok)
        throw new Error(stateJson?.detail || `State error ${stateRes.status}`)
      if (!capRes.ok)
        throw new Error(capJson?.detail || `Captures error ${capRes.status}`)
      if (!revRes.ok)
        throw new Error(revJson?.detail || `Revisions error ${revRes.status}`)

      setStateResp(stateJson)
      setCapturesResp(capJson)
      setRevisionsResp(revJson)
    } catch (e: any) {
      setError(e?.message || 'Failed to load Ditto data')
    } finally {
      setLoading(false)
    }
  }

  const lastCaptureImageUrl =
    stateResp?.lastCapture?.image_url &&
    `${API_BASE}${stateResp.lastCapture.image_url}`

  return (
    <div className="flex h-full flex-col bg-slate-50/60">
      <div className="flex flex-1 flex-col gap-4 overflow-auto p-6">
        {/* Query bar */}
        <div className="flex flex-wrap items-end gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
          <div>
            <label className="block text-[11px] font-medium text-slate-700">
              Camera ID
            </label>
            <input
              className="mt-1 w-40 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-900 focus:border-slate-900 focus:outline-none"
              value={cameraId}
              onChange={(e) => setCameraId(e.target.value)}
              placeholder="camera-01"
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-slate-700">
              Image ID (DB id)
            </label>
            <input
              className="mt-1 w-32 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-900 focus:border-slate-900 focus:outline-none"
              value={imageId}
              onChange={(e) => setImageId(e.target.value)}
              placeholder="1"
            />
          </div>
          <button
            onClick={handleLoad}
            disabled={loading}
            className="h-9 rounded-lg bg-slate-900 px-4 text-[11px] font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? 'Loading…' : 'Load Ditto Image Thing'}
          </button>
          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-[11px] text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* 3-column layout */}
        <div className="grid gap-4 md:grid-cols-3">
          {/* State + last capture */}
          <div className="space-y-3">
            <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Detections & Last Capture
              </h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Live state for the selected Ditto image thing.
              </p>
              {!stateResp && !loading && (
                <p className="mt-3 text-[11px] text-slate-400">
                  Enter camera + image id and load Ditto data.
                </p>
              )}
              {stateResp && (
                <>
                  {lastCaptureImageUrl && (
                    <div className="mt-3 overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                      {/* eslint-disable-next-line jsx-a11y/alt-text */}
                      <img
                        src={lastCaptureImageUrl}
                        className="max-h-52 w-full object-contain"
                      />
                    </div>
                  )}
                  <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-[10px] text-slate-800">
                    {JSON.stringify(stateResp, null, 2)}
                  </pre>
                </>
              )}
            </div>
          </div>

          {/* Captures */}
          <div className="space-y-3">
            <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Captures (image thing)
              </h2>
              <p className="mt-1 text-[11px] text-slate-500">
                History + lastCapture as stored in Ditto for this image thing.
              </p>

              {!capturesResp && !loading && (
                <p className="mt-3 text-[11px] text-slate-400">
                  Load Ditto data to see captures.
                </p>
              )}
              {capturesResp && (
                <>
                  <div className="mt-2 text-[11px] text-slate-500">
                    Total: {capturesResp.total} • Returned:{' '}
                    {capturesResp.returned} • Order:{' '}
                    {capturesResp.order?.toUpperCase?.()}
                  </div>
                  <div className="mt-3 max-h-72 space-y-3 overflow-auto">
                    {capturesResp.captures?.map((c: any, idx: number) => {
                      const url = c.image_url ? `${API_BASE}${c.image_url}` : null
                      return (
                        <div
                          key={idx}
                          className="flex items-center gap-3 rounded-lg border border-slate-200 bg-slate-50 p-2"
                        >
                          {url && (
                            <div className="h-12 w-12 overflow-hidden rounded-md bg-white">
                              {/* eslint-disable-next-line jsx-a11y/alt-text */}
                              <img
                                src={url}
                                className="h-full w-full object-cover"
                              />
                            </div>
                          )}
                          <div className="flex-1">
                            <div className="text-[11px] font-semibold text-slate-800">
                              {c.captured_at || 'No timestamp'}
                            </div>
                            <div className="text-[10px] text-slate-500">
                              lat: {c.lat}, lon: {c.lon}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Revisions */}
          <div className="space-y-3">
            <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Thing Revisions
              </h2>
              <p className="mt-1 text-[11px] text-slate-500">
                Historical revisions of this image&apos;s Ditto document.
              </p>
              {!revisionsResp && !loading && (
                <p className="mt-3 text-[11px] text-slate-400">
                  Load Ditto data to inspect revisions.
                </p>
              )}
              {revisionsResp && (
                <>
                  <div className="mt-2 text-[11px] text-slate-500">
                    Revisions: {revisionsResp.revisions_count}
                  </div>
                  <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-50 p-3 text-[10px] text-slate-800">
                    {JSON.stringify(revisionsResp, null, 2)}
                  </pre>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
