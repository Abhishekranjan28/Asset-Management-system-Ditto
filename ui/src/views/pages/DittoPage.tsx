// src/views/pages/DittoPage.tsx
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

  const detections = stateResp?.detections ?? null
  const detectionObjects = (detections?.objects as any[]) ?? []
  const prevObjects = (detections?.prev?.objects as any[]) ?? []
  const changedSincePrevious = !!detections?.changed_since_previous
  const changeReason = detections?.change_reason || ''

  const captures = (capturesResp?.captures as any[]) ?? []
  const revisions = (revisionsResp?.revisions as any[]) ?? []

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
          {/* Column 1: Detections + Last capture */}
          <div className="space-y-3">
            <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-100">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Detections &amp; Last Capture
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

                  {/* detections summary */}
                  <div className="mt-3 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={[
                          'inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold',
                          changedSincePrevious
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-emerald-50 text-emerald-700 border border-emerald-200',
                        ].join(' ')}
                      >
                        <span className="mr-1 h-1.5 w-1.5 rounded-full bg-current" />
                        {changedSincePrevious
                          ? 'Changed vs previous'
                          : 'No change vs previous'}
                      </span>
                      {changeReason && (
                        <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[10px] text-slate-600 border border-slate-200">
                          Reason: {changeReason}
                        </span>
                      )}
                    </div>

                    {detections?.caption && (
                      <div className="rounded-lg bg-slate-50 px-3 py-2 text-[11px] text-slate-800 border border-slate-100">
                        {detections.caption}
                      </div>
                    )}

                    {stateResp.lastCapture && (
                      <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                        <InfoCell
                          label="Captured at"
                          value={stateResp.lastCapture.captured_at}
                        />
                        <InfoCell
                          label="Coordinates"
                          value={
                            stateResp.lastCapture.lat != null &&
                            stateResp.lastCapture.lon != null
                              ? `${stateResp.lastCapture.lat}, ${stateResp.lastCapture.lon}`
                              : '—'
                          }
                        />
                        <InfoCell
                          label="Resolution"
                          value={
                            stateResp.lastCapture.width &&
                            stateResp.lastCapture.height
                              ? `${stateResp.lastCapture.width} × ${stateResp.lastCapture.height}`
                              : '—'
                          }
                        />
                        <InfoCell
                          label="Size"
                          value={
                            stateResp.lastCapture.size_bytes
                              ? `${Math.round(
                                  stateResp.lastCapture.size_bytes / 1024,
                                )} KB`
                              : '—'
                          }
                        />
                      </div>
                    )}
                  </div>

                  {/* Objects table */}
                  <div className="mt-3">
                    <div className="mb-1 flex items-center justify-between">
                      <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                        Detected objects
                      </h3>
                      <span className="text-[10px] text-slate-400">
                        {detectionObjects.length} objects
                      </span>
                    </div>
                    {detectionObjects.length === 0 ? (
                      <p className="text-[11px] text-slate-400">
                        No objects in current detections.
                      </p>
                    ) : (
                      <div className="max-h-44 overflow-auto rounded-lg border border-slate-100">
                        <table className="min-w-full border-collapse text-[11px]">
                          <thead className="bg-slate-50">
                            <tr>
                              <Th>Label</Th>
                              <Th>State</Th>
                              <Th>Confidence</Th>
                              <Th>BBox (x, y, w, h)</Th>
                            </tr>
                          </thead>
                          <tbody>
                            {detectionObjects.map((o, idx) => (
                              <tr
                                key={idx}
                                className="border-t border-slate-100 bg-white"
                              >
                                <Td>{o.label}</Td>
                                <Td className="capitalize">{o.state}</Td>
                                <Td>{(o.confidence * 100).toFixed(1)}%</Td>
                                <Td>
                                  {Array.isArray(o.bbox)
                                    ? o.bbox
                                        .map((v: number) => v.toFixed(2))
                                        .join(', ')
                                    : '—'}
                                </Td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Previous objects table */}
                  {prevObjects.length > 0 && (
                    <div className="mt-3">
                      <div className="mb-1 flex items-center justify-between">
                        <h3 className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                          Previous objects
                        </h3>
                        <span className="text-[10px] text-slate-400">
                          {prevObjects.length} objects
                        </span>
                      </div>
                      <div className="max-h-40 overflow-auto rounded-lg border border-slate-100">
                        <table className="min-w-full border-collapse text-[11px]">
                          <thead className="bg-slate-50">
                            <tr>
                              <Th>Label</Th>
                              <Th>State</Th>
                              <Th>Confidence</Th>
                              <Th>BBox (x, y, w, h)</Th>
                            </tr>
                          </thead>
                          <tbody>
                            {prevObjects.map((o, idx) => (
                              <tr
                                key={idx}
                                className="border-t border-slate-100 bg-white"
                              >
                                <Td>{o.label}</Td>
                                <Td className="capitalize">{o.state}</Td>
                                <Td>{(o.confidence * 100).toFixed(1)}%</Td>
                                <Td>
                                  {Array.isArray(o.bbox)
                                    ? o.bbox
                                        .map((v: number) => v.toFixed(2))
                                        .join(', ')
                                    : '—'}
                                </Td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Column 2: Captures (image thing) */}
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

                  {captures.length === 0 ? (
                    <p className="mt-3 text-[11px] text-slate-400">
                      No capture history for this thing.
                    </p>
                  ) : (
                    <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-100">
                      <table className="min-w-full border-collapse text-[11px]">
                        <thead className="bg-slate-50">
                          <tr>
                            <Th>Captured at</Th>
                            <Th>Lat</Th>
                            <Th>Lon</Th>
                            <Th className="text-center">Image</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {captures.map((c: any, idx: number) => {
                            const url = c.image_url
                              ? `${API_BASE}${c.image_url}`
                              : null
                            return (
                              <tr
                                key={idx}
                                className="border-t border-slate-100 bg-white"
                              >
                                <Td>{c.captured_at || '—'}</Td>
                                <Td>
                                  {c.lat != null ? c.lat.toFixed(6) : '—'}
                                </Td>
                                <Td>
                                  {c.lon != null ? c.lon.toFixed(6) : '—'}
                                </Td>
                                <Td className="text-center">
                                  {url ? (
                                    <span className="inline-flex h-6 w-8 items-center justify-center overflow-hidden rounded border border-slate-200 bg-slate-50">
                                      {/* eslint-disable-next-line jsx-a11y/alt-text */}
                                      <img
                                        src={url}
                                        className="h-full w-full object-cover"
                                      />
                                    </span>
                                  ) : (
                                    '—'
                                  )}
                                </Td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Column 3: Thing revisions – FULL DATA in table */}
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

                  {revisions.length === 0 ? (
                    <p className="mt-3 text-[11px] text-slate-400">
                      No revisions recorded for this thing.
                    </p>
                  ) : (
                    <div className="mt-3 max-h-72 overflow-auto rounded-lg border border-slate-100">
                      <table className="min-w-full border-collapse text-[11px]">
                        <thead className="bg-slate-50">
                          <tr>
                            <Th>#</Th>
                            <Th>Thing ID</Th>
                            <Th>Policy ID</Th>
                            <Th>Revision JSON</Th>
                          </tr>
                        </thead>
                        <tbody>
                          {revisions.map((rev: any, idx: number) => (
                            <tr
                              key={idx}
                              className="border-t border-slate-100 bg-white align-top"
                            >
                              <Td>{idx + 1}</Td>
                              <Td>{rev.thingId || '—'}</Td>
                              <Td>{rev.policyId || '—'}</Td>
                              <Td>
                                <pre className="max-h-40 overflow-auto rounded bg-slate-50 p-2 text-[10px] text-slate-800">
                                  {JSON.stringify(rev, null, 2)}
                                </pre>
                              </Td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ---- tiny table helpers ---- */

const Th: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <th
    className={
      'px-3 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-slate-500 ' +
      className
    }
  >
    {children}
  </th>
)

const Td: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <td className={'px-3 py-1.5 align-top text-[11px] text-slate-800 ' + className}>
    {children}
  </td>
)

const InfoCell: React.FC<{ label: string; value: React.ReactNode }> = ({
  label,
  value,
}) => (
  <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1.5">
    <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
      {label}
    </div>
    <div className="mt-0.5 text-[11px] font-semibold text-slate-900 break-all">
      {value || '—'}
    </div>
  </div>
)
