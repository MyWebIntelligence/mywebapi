import { useState, useEffect, useRef } from 'react'
import { getJobStatus } from '../api/operationsApi'

/**
 * Poll a job endpoint until completion or failure.
 * @param {string|null} jobId - The job ID to poll (null to disable)
 * @param {number} interval - Polling interval in ms (default 3000)
 * @returns {{ status, progress, result, error, isPolling }}
 */
export default function useJobPolling(jobId, interval = 3000) {
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isPolling, setIsPolling] = useState(false)
  const timerRef = useRef(null)

  useEffect(() => {
    if (!jobId) {
      setStatus(null)
      setProgress(null)
      setResult(null)
      setError(null)
      setIsPolling(false)
      return
    }

    setIsPolling(true)
    setError(null)

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId)
        setStatus(data.status)
        setProgress(data.progress ?? null)

        if (data.status === 'completed' || data.status === 'success') {
          setResult(data.result ?? data)
          setIsPolling(false)
          return
        }

        if (data.status === 'failed' || data.status === 'error') {
          setError(data.error || data.message || 'Job failed')
          setIsPolling(false)
          return
        }

        // Continue polling
        timerRef.current = setTimeout(poll, interval)
      } catch (err) {
        setError(err.message || 'Failed to fetch job status')
        setIsPolling(false)
      }
    }

    poll()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [jobId, interval])

  return { status, progress, result, error, isPolling }
}
