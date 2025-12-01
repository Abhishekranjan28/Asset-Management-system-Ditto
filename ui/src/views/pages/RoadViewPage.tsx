// src/views/pages/RoadViewPage.tsx
import React, { useEffect, useMemo, useState } from 'react'
import { API_BASE } from '../../config'
import type { ImageRow, RoadPoint } from '../../types'
import { LegendPill } from '../../components/LegendPill'
import { InfoRow } from '../../components/InfoRow'

export const RoadViewPage: React.FC = () => {
  const [points, setPoints] = useState<RoadPoint[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<RoadPoint | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE}/images`)
        if (!res.ok) throw new Error(`Backend error ${res.status}`)
        const data: ImageRow[] = await res.json()

        const pts: RoadPoint[] = data.map((row, idx) => {
          const isChanged = !!row.changed
          const fullImageUrl = row.image_url ? `${API_BASE}${row.image_url}` : null
          const subtitle =
            row.caption ||
            row.reason ||
            (isChanged ? 'Change detected vs previous capture' : 'No major change detected')

          return {
            id: String(row.id),
            lat: row.lat,
            lng: row.lon,
            order: idx,
            title: `${row.camera_id} • #${row.id}`,
            subtitle,
            time: row.captured_at,
            iconText: isChanged ? 'Δ' : '•',
            meta: { ...row, image_url: fullImageUrl },
          }
        })

        if (!cancelled) setPoints(pts)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load images')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  const sorted = useMemo(() => {
    const copy = [...points]
    copy.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    return copy
  }, [points])

  // Road width extends with number of points
  const roadWidth = useMemo(() => {
    const n = sorted.length || 1
    return Math.max(n * 220, 1200)
  }, [sorted.length])

  return (
    <div className="flex h-full flex-col bg-slate-50/60">
      <div className="flex flex-1 overflow-hidden">
        {/* Road area */}
        <div className="relative flex-1 overflow-x-auto bg-slate-100/80">
          <div className="inline-block px-6 py-8">
            <div className="relative mx-auto">
              <div className="relative h-60" style={{ width: roadWidth }}>
                {/* Road surface */}
                <div
                  className="
                    absolute inset-y-6 left-0 right-0
                    rounded-[999px]
                    bg-[radial-gradient(circle_at_10%_0%,#4b5563_0,#111827_55%,#020617_100%)]
                    shadow-[0_20px_50px_rgba(15,23,42,0.7)]
                  "
                >
                  {/* Edge lines */}
                  <div className="pointer-events-none absolute inset-y-5 left-5 right-5 rounded-[999px] border border-slate-500/70" />
                  <div className="pointer-events-none absolute inset-y-8 left-10 right-10 rounded-[999px] border border-slate-600/70" />

                  {/* Center dashed line (muted yellow) */}
                  <div className="pointer-events-none absolute inset-x-24 top-1/2 -translate-y-1/2">
                    <div className="h-[3px] rounded-full bg-slate-800">
                      <div className="h-[3px] rounded-full bg-[repeating-linear-gradient(to_right,transparent,transparent_16px,#eab308_16px,#eab308_30px)] opacity-85" />
                    </div>
                  </div>

                  {/* Vehicles / captures */}
                  <div className="relative flex h-full items-center gap-10 px-20">
                    {loading && (
                      <div className="text-xs text-slate-200">
                        Loading captures…
                      </div>
                    )}
                    {!loading && error && (
                      <div className="text-xs text-red-200">{error}</div>
                    )}
                    {!loading && !error && sorted.length === 0 && (
                      <div className="text-xs text-slate-200">
                        No captures yet.
                      </div>
                    )}

                    {!loading &&
                      !error &&
                      sorted.length > 0 &&
                      sorted.map((p, idx) => {
                        const hasImage = !!p.meta?.image_url
                        const isSelected = selected?.id === p.id
                        const changed = !!p.meta?.changed

                        return (
                          <button
                            key={p.id}
                            type="button"
                            onClick={() => setSelected(p)}
                            className="group relative flex flex-col items-center gap-2 focus:outline-none"
                          >
                            {/* Vehicle + shadow */}
                            <div className="flex flex-col items-center gap-1">
                              <div className="h-1.5 w-12 rounded-full bg-black/45 blur-sm" />
                              <div
                                className={[
                                  'relative flex h-16 w-16 items-center justify-center overflow-hidden rounded-md bg-slate-50 shadow-[0_14px_24px_rgba(0,0,0,0.55)]',
                                  isSelected
                                    ? 'ring-2 ring-sky-400'
                                    : changed
                                    ? 'ring-2 ring-red-400'
                                    : 'ring-2 ring-slate-300',
                                ].join(' ')}
                              >
                                {hasImage ? (
                                  // eslint-disable-next-line jsx-a11y/alt-text
                                  <img
                                    src={p.meta?.image_url}
                                    className="h-full w-full object-cover"
                                  />
                                ) : (
                                  <span className="text-sm font-semibold text-slate-800">
                                    {p.iconText}
                                  </span>
                                )}
                                {/* Status indicator */}
                                <span
                                  className={[
                                    'absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold shadow-md',
                                    changed
                                      ? 'bg-red-500 text-white'
                                      : 'bg-emerald-500 text-white',
                                  ].join(' ')}
                                >
                                  {changed ? 'Δ' : '•'}
                                </span>
                              </div>
                            </div>

                            {/* Label below road */}
                            <div className="pointer-events-none mt-2 flex max-w-[140px] flex-col items-center">
                              <span className="truncate text-[10px] font-medium text-slate-50 drop-shadow">
                                {p.meta?.camera_id ?? p.title ?? p.id}
                              </span>
                              <span className="truncate text-[10px] text-slate-200 drop-shadow">
                                #{idx + 1} · {p.time?.slice(0, 10) ?? ''}
                              </span>
                            </div>

                            {/* Tooltip */}
                            <div className="pointer-events-none absolute -top-32 z-10 hidden min-w-[220px] max-w-xs rounded-lg bg-white p-2 text-left text-[11px] shadow-xl ring-1 ring-slate-200 group-hover:block">
                              <div className="font-semibold text-slate-900">
                                {p.title ?? p.id}
                              </div>
                              {p.subtitle && (
                                <div className="mt-1 text-[10px] text-slate-600">
                                  {p.subtitle}
                                </div>
                              )}
                              <div className="mt-1 text-[10px] text-slate-500">
                                lat: {p.lat.toFixed(5)}, lon:{' '}
                                {p.lng.toFixed(5)}
                              </div>
                            </div>
                          </button>
                        )
                      })}
                  </div>
                </div>

                {/* Legend floating above road */}
                <div className="pointer-events-none absolute left-6 top-0 flex gap-2">
                  <LegendPill color="alert" label="Change detected" />
                  <LegendPill color="normal" label="Baseline capture" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Details drawer (right) */}
        <aside
          className={`relative shrink-0 border-l border-slate-200 bg-white transition-[width] duration-300 ${
            selected ? 'w-full md:w-[420px]' : 'w-0'
          }`}
        >
          <div className="absolute inset-0 overflow-y-auto">
            {selected && (
              <div className="flex h-full flex-col">
                <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
                  <div>
                    <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                      Capture details
                    </div>
                    <h3 className="text-sm font-semibold text-slate-900">
                      {selected.title ?? selected.id}
                    </h3>
                    {selected.subtitle && (
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {selected.subtitle}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => setSelected(null)}
                    className="rounded-full border border-slate-200 px-3 py-1 text-[11px] text-slate-700 hover:bg-slate-50"
                  >
                    Close
                  </button>
                </div>

                <div className="space-y-4 p-4">
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <InfoRow
                      label="Camera ID"
                      value={selected.meta?.camera_id ?? '—'}
                    />
                    <InfoRow
                      label="Status"
                      value={
                        selected.meta?.changed
                          ? 'Change detected'
                          : 'No major change'
                      }
                    />
                    <InfoRow
                      label="Reason"
                      value={selected.meta?.reason || '—'}
                    />
                    <InfoRow
                      label="Captured At"
                      value={selected.time ?? '—'}
                    />
                    <InfoRow
                      label="Latitude"
                      value={selected.lat.toFixed(6)}
                    />
                    <InfoRow
                      label="Longitude"
                      value={selected.lng.toFixed(6)}
                    />
                    <InfoRow
                      label="Image ID"
                      value={selected.meta?.id ?? selected.id}
                    />
                  </div>

                  {selected.meta?.image_url && (
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        Capture image
                      </div>
                      <div className="mt-1 overflow-hidden rounded-lg border border-slate-200 bg-slate-50">
                        {/* eslint-disable-next-line jsx-a11y/alt-text */}
                        <img
                          src={selected.meta.image_url}
                          className="max-h-72 w-full object-contain"
                        />
                      </div>
                    </div>
                  )}

                  {(selected.meta?.caption || '').trim() && (
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        Caption
                      </div>
                      <p className="mt-1 rounded-lg bg-slate-50 px-3 py-2 text-[11px] text-slate-800">
                        {selected.meta.caption}
                      </p>
                    </div>
                  )}

                  {selected.meta && (
                    <div>
                      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                        Raw metadata
                      </div>
                      <pre className="mt-1 max-h-64 overflow-auto rounded-lg bg-slate-50 p-3 text-[10px] text-slate-800">
                        {JSON.stringify(selected.meta, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
