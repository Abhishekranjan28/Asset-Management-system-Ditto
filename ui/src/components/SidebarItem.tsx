// src/components/SidebarItem.tsx
import React from 'react'

type SidebarItemProps = {
  active: boolean
  label: string
  icon?: React.ReactNode
  collapsed: boolean
  onClick: () => void
}

export const SidebarItem: React.FC<SidebarItemProps> = ({
  active,
  label,
  icon,
  collapsed,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      className={[
        'group flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium transition-colors',
        active
          ? 'bg-slate-900 text-slate-50 shadow-sm'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
      ].join(' ')}
    >
      <span
        className={[
          'flex h-7 w-7 items-center justify-center rounded-md text-base',
          active
            ? 'bg-slate-800 text-slate-50'
            : 'bg-slate-100 text-slate-700 group-hover:bg-slate-200',
        ].join(' ')}
      >
        {icon}
      </span>
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  )
}
