'use client'

import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { api, FormattedResumeResult } from '@/lib/api'
import { UploadIcon, DownloadIcon, FileTextIcon, SearchIcon, CheckCircleIcon, AlertTriangleIcon } from 'lucide-react'

const STAGES = [
  { key: 'upload', label: 'Uploading resume' },
  { key: 'parse', label: 'Extracting resume content' },
  { key: 'research', label: 'Researching facilities (type, bed size, EMR)' },
  { key: 'format', label: 'Building HonorVet standard document' },
]

const confidenceColor: Record<string, string> = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-red-100 text-red-800',
}

export default function HonorVetTab() {
  const [file, setFile] = useState<File | null>(null)
  const [processing, setProcessing] = useState(false)
  const [stageIndex, setStageIndex] = useState(0)
  const [result, setResult] = useState<FormattedResumeResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const onDrop = useCallback((files: File[]) => { if (files[0]) { setFile(files[0]); setResult(null); setError(null) } }, [])
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': [],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': [],
      'text/plain': [],
      'image/jpeg': [],
      'image/png': [],
    },
    maxFiles: 1,
  })

  async function handleFormat() {
    if (!file) return
    setProcessing(true)
    setError(null)
    setResult(null)
    setStageIndex(1)
    const researchTimer = setTimeout(() => setStageIndex(2), 1500)
    const formatTimer = setTimeout(() => setStageIndex(3), 6000)
    try {
      const res = await api.format(file)
      setResult(res)
    } catch (e: any) {
      setError(e.message || 'Failed to format resume')
    } finally {
      clearTimeout(researchTimer)
      clearTimeout(formatTimer)
      setProcessing(false)
      setStageIndex(0)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">HonorVet Standard Formatter</h1>
        <p className="text-gray-500 mt-1">Upload a raw resume — we'll reformat it into HonorVet standard formatting and research each facility's type, bed size, and EMR system.</p>
      </div>

      {!result && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400'}`}
          >
            <input {...getInputProps()} />
            <UploadIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
            {file ? (
              <p className="text-sm text-gray-700 font-medium">{file.name}</p>
            ) : (
              <p className="text-sm text-gray-500">Drag & drop a resume (PDF, DOCX, TXT, JPEG, PNG), or click to browse</p>
            )}
          </div>

          <button
            onClick={handleFormat}
            disabled={!file || processing}
            className="mt-4 w-full flex items-center justify-center gap-2 bg-blue-600 text-white px-4 py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium"
          >
            <FileTextIcon className="w-4 h-4" />
            {processing ? 'Formatting…' : 'Format Resume'}
          </button>

          {processing && (
            <div className="mt-5 space-y-2">
              {STAGES.map((s, i) => (
                <div key={s.key} className="flex items-center gap-2 text-sm">
                  {i < stageIndex ? (
                    <CheckCircleIcon className="w-4 h-4 text-green-600" />
                  ) : i === stageIndex ? (
                    <SearchIcon className="w-4 h-4 text-blue-600 animate-pulse" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-gray-300" />
                  )}
                  <span className={i <= stageIndex ? 'text-gray-800' : 'text-gray-400'}>{s.label}</span>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="mt-4 flex items-start gap-2 bg-red-50 text-red-700 text-sm p-3 rounded-lg">
              <AlertTriangleIcon className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6 flex items-center justify-between">
            <div>
              <p className="font-bold text-gray-900">{result.resume.full_name}{result.resume.credentials_suffix ? `, ${result.resume.credentials_suffix}` : ''}</p>
              <p className="text-sm text-gray-500">{[result.resume.phone, result.resume.email, result.resume.location].filter(Boolean).join(' · ')}</p>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={api.downloadUrl(result.download_filename)}
                className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm font-medium"
              >
                <DownloadIcon className="w-4 h-4" /> Download .docx
              </a>
              <button
                onClick={() => { setResult(null); setFile(null) }}
                className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 text-sm font-medium"
              >
                Format another
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="font-bold text-gray-900 mb-3">Facility research — verify before sending</h2>
            <div className="space-y-4">
              {result.resume.experience.map((job, i) => (
                <div key={i} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-semibold text-gray-900 text-sm">{job.facility_name}{job.city ? `, ${job.city}, ${job.state}` : ''}</p>
                    {job.research_confidence && (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${confidenceColor[job.research_confidence] || 'bg-gray-100 text-gray-700'}`}>
                        {job.research_confidence} confidence
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-sm">
                    <div><span className="text-gray-400">Type: </span>{job.type_of_facility || <span className="text-gray-400 italic">unknown</span>}</div>
                    <div><span className="text-gray-400">Trauma: </span>{job.trauma_level || <span className="text-gray-400 italic">unknown</span>}</div>
                    <div><span className="text-gray-400">Beds: </span>{job.bed_size ?? <span className="text-gray-400 italic">unknown</span>}</div>
                    <div><span className="text-gray-400">EMR: </span>{job.emr_system || <span className="text-gray-400 italic">unknown</span>}</div>
                  </div>
                  {job.research_sources && job.research_sources.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {job.research_sources.map((src, si) => (
                        <a key={si} href={src} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-600 hover:underline truncate max-w-[220px]">
                          {src}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
