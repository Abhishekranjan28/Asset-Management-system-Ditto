// src/components/SidebarItem.tsx
import React from 'react'

type SidebarItemProps = {
  active: boolean
  label: string
  collapsed: boolean
  onClick: () => void
}

export const SidebarItem: React.FC<SidebarItemProps> = ({
  active,
  label,
  collapsed,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      className={[
        'group flex w-full items-center rounded-lg px-2 py-2 text-xs font-medium transition-colors',
        active
          ? 'bg-slate-900/95 text-slate-50 shadow-sm'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
      ].join(' ')}
    >
      {/* Active indicator bar */}
      <span
        className={[
          'mr-2 h-6 w-[3px] rounded-full transition-colors',
          active ? 'bg-sky-400' : 'bg-transparent group-hover:bg-slate-300',
        ].join(' ')}
      />
      {!collapsed && (
        <span className="truncate font-medium tracking-wide">
          {label}
        </span>
      )}
    </button>
  )
}
