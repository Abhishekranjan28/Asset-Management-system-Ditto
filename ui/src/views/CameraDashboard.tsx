// src/views/CameraDashboard.tsx
import React, { useState } from 'react'
import { API_BASE } from '../config'
import { SidebarItem } from '../components/SidebarItem'
import { UploadPage } from './pages/UploadPage'
import { RoadViewPage } from './pages/RoadViewPage'
import { DittoPage } from './pages/DittoPage'

type PageKey = 'upload' | 'road' | 'ditto'

const CameraDashboard: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [page, setPage] = useState<PageKey>('upload')

  const pageTitle =
    page === 'upload'
      ? 'Image Ingestion'
      : page === 'road'
      ? 'Route Overview'
      : 'Ditto Device State'

  const pageSubtitle =
    page === 'upload'
      ? 'Upload new camera captures and trigger analysis.'
      : page === 'road'
      ? 'Visualize captures along the route and inspect change events.'
      : 'Inspect live device state and historical revisions from Ditto.'

  return (
    <div className="flex h-screen w-screen bg-slate-50 text-slate-900">
      {/* Sidebar */}
      <div
        className={`relative flex flex-col border-r border-slate-200 bg-white/95 backdrop-blur-sm transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-16'
        }`}
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-3 py-3">
          {sidebarOpen ? (
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white">
                NN
              </div>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                  NaturNest
                </div>
                <div className="text-[11px] font-medium text-slate-900">
                  Camera Analytics
                </div>
              </div>
            </div>
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white">
              NN
            </div>
          )}

          <button
            onClick={() => setSidebarOpen((s) => !s)}
            className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 text-[10px] text-slate-600 hover:bg-slate-50"
            title={sidebarOpen ? 'Collapse' : 'Expand'}
          >
            {sidebarOpen ? '‹' : '›'}
          </button>
        </div>

        {/* Nav */}
        <nav className="mt-3 flex-1 space-y-1 px-2">
          <SidebarItem
            active={page === 'upload'}
            label="Image Ingestion"
            icon={<span>⬆️</span>}
            collapsed={!sidebarOpen}
            onClick={() => setPage('upload')}
          />
          <SidebarItem
            active={page === 'road'}
            label="Route Overview"
            icon={<span>🛣️</span>}
            collapsed={!sidebarOpen}
            onClick={() => setPage('road')}
          />
          <SidebarItem
            active={page === 'ditto'}
            label="Ditto State"
            icon={<span>🧩</span>}
            collapsed={!sidebarOpen}
            onClick={() => setPage('ditto')}
          />
        </nav>

        {/* Footer */}
        <div className="border-t border-slate-200 px-3 py-2 text-[10px] text-slate-500">
          {sidebarOpen && (
            <>
              <div className="flex items-center justify-between">
                <span>Environment</span>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                  DE · Pilot
                </span>
              </div>
              <div className="mt-1 truncate text-[10px]">
                Backend: <span className="font-mono text-[9px]">{API_BASE}</span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar / page header */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-white/90 px-6 py-3 backdrop-blur-sm">
          <div>
            <div className="flex items-center gap-2 text-[11px] text-slate-500">
              <span className="uppercase tracking-wide">Operations</span>
              <span className="text-slate-300">/</span>
              <span className="font-medium text-slate-700">{pageTitle}</span>
            </div>
            <h1 className="mt-0.5 text-sm font-semibold text-slate-900">
              {pageTitle}
            </h1>
            <p className="mt-0.5 text-[11px] text-slate-500">{pageSubtitle}</p>
          </div>

          <div className="flex items-center gap-3">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-medium text-slate-700">
              Status: <span className="text-emerald-600">Connected</span>
            </span>
          </div>
        </div>

        {/* Page body */}
        <div className="flex-1 overflow-hidden">
          {page === 'upload' && <UploadPage />}
          {page === 'road' && <RoadViewPage />}
          {page === 'ditto' && <DittoPage />}
        </div>
      </div>
    </div>
  )
}

export default CameraDashboard
