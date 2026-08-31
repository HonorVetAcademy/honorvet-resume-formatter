'use client'

import { useState } from 'react'
import HonorVetTab from '@/components/HonorVetTab'
import RightSourcingTab from '@/components/RightSourcingTab'

const TABS = [
  { key: 'honorvet', label: 'HonorVet Standard' },
  { key: 'rightsourcing', label: 'RightSourcing' },
] as const

type TabKey = typeof TABS[number]['key']

export default function Home() {
  const [tab, setTab] = useState<TabKey>('honorvet')

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'honorvet' ? <HonorVetTab /> : <RightSourcingTab />}
    </div>
  )
}
