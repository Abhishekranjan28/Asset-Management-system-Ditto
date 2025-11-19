// src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import CameraDashboard from './views/CameraDashboard'

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <div className="h-screen w-screen">
      <CameraDashboard />
    </div>
  </React.StrictMode>,
)
