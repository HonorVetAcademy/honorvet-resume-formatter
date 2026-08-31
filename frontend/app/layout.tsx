import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'HonorVet Resume Formatter',
  description: 'Reformat resumes into HonorVet standard formatting with AI-researched facility data',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gray-50">
          <header className="bg-white border-b border-gray-200">
            <div className="max-w-4xl mx-auto px-8 py-4">
              <p className="font-bold text-gray-900 text-sm">HonorVet Resume Formatter</p>
              <p className="text-xs text-gray-500">Powered by Claude</p>
            </div>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  )
}
