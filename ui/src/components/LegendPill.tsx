// src/components/LegendPill.tsx
import React from 'react'

export const LegendPill: React.FC<{ color: 'alert' | 'normal'; label: string }> = ({
  color,
  label,
}) => {
  const base =
    'inline-flex items-center gap-1 rounded-full border px-2 py-1 text-[10px] font-medium'
  const theme =
    color === 'alert'
      ? 'border-red-200 bg-red-50 text-red-700'
      : 'border-emerald-200 bg-emerald-50 text-emerald-700'

  return (
    <span className={`${base} ${theme}`}>
      <span
        className={[
          'h-1.5 w-1.5 rounded-full',
          color === 'alert' ? 'bg-red-500' : 'bg-emerald-500',
        ].join(' ')}
      />
      <span>{label}</span>
    </span>
  )
}
