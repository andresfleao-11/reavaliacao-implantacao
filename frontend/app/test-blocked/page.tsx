'use client'

import { useState, useEffect } from 'react'

export default function TestBlockedPage() {
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    console.log('Starting fetch...')

    fetch('http://localhost:8000/api/blocked-domains')
      .then(response => {
        console.log('Response received:', response)
        return response.json()
      })
      .then(data => {
        console.log('Data parsed:', data)
        setData(data)
        setLoading(false)
      })
      .catch(err => {
        console.error('Error occurred:', err)
        setError(err.message)
        setLoading(false)
      })
  }, [])

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Test Blocked Domains API</h1>

      {loading && <p>Loading...</p>}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          Error: {error}
        </div>
      )}

      {data && (
        <div>
          <p className="mb-2">Found {data.length} domains:</p>
          <pre className="bg-gray-100 p-4 rounded overflow-auto">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
