// src/components/InfoRow.tsx
import React from 'react'

export const InfoRow: React.FC<{ label: string; value: React.ReactNode }> = ({
  label,
  value,
}) => {
  return (
    <div className="flex flex-col rounded-lg border border-slate-100 bg-slate-50/70 px-3 py-2">
      <span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <span className="mt-0.5 text-[11px] font-semibold text-slate-900 break-all">
        {value}
      </span>
    </div>
  )
}
