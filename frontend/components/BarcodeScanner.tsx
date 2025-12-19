'use client'

import { useState, useRef, useEffect, useCallback } from 'react'

interface BarcodeScannerProps {
  isOpen: boolean
  onClose: () => void
  onScan: (code: string) => void
}

export default function BarcodeScanner({ isOpen, onClose, onScan }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string>('')
  const [scanning, setScanning] = useState(false)
  const scanIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const stopCamera = useCallback(() => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current)
      scanIntervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop())
      streamRef.current = null
    }
    setScanning(false)
  }, [])

  const startCamera = useCallback(async () => {
    try {
      setError('')
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1280 },
          height: { ideal: 720 }
        }
      })

      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
        setScanning(true)
        startScanning()
      }
    } catch (err: any) {
      console.error('Erro ao acessar câmera:', err)
      if (err.name === 'NotAllowedError') {
        setError('Permissão de câmera negada. Permita o acesso à câmera.')
      } else if (err.name === 'NotFoundError') {
        setError('Câmera não encontrada.')
      } else {
        setError('Erro ao acessar a câmera: ' + err.message)
      }
    }
  }, [])

  const startScanning = useCallback(async () => {
    // Importa ZXing dinamicamente para evitar problemas de SSR
    const { BrowserMultiFormatReader } = await import('@zxing/browser')
    const codeReader = new BrowserMultiFormatReader()

    if (videoRef.current) {
      try {
        codeReader.decodeFromVideoElement(videoRef.current, (result, error) => {
          if (result) {
            const code = result.getText()
            // Extrai apenas números do código de barras
            const numericCode = code.replace(/\D/g, '')
            if (numericCode) {
              onScan(numericCode)
              stopCamera()
              onClose()
            }
          }
        })
      } catch (err) {
        console.error('Erro no scanner:', err)
      }
    }
  }, [onScan, onClose, stopCamera])

  useEffect(() => {
    if (isOpen) {
      startCamera()
    } else {
      stopCamera()
    }

    return () => {
      stopCamera()
    }
  }, [isOpen, startCamera, stopCamera])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 bg-black">
      {/* Header */}
      <div className="absolute top-0 left-0 right-0 z-10 bg-gradient-to-b from-black/70 to-transparent p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-white text-lg font-medium">Escanear Código de Barras</h2>
          <button
            onClick={() => {
              stopCamera()
              onClose()
            }}
            className="p-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors"
          >
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Video container */}
      <div className="relative h-full flex items-center justify-center">
        {error ? (
          <div className="text-center p-6">
            <div className="bg-red-500/20 rounded-lg p-4 mb-4">
              <svg className="w-12 h-12 text-red-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <p className="text-red-300">{error}</p>
            </div>
            <button
              onClick={startCamera}
              className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        ) : (
          <>
            <video
              ref={videoRef}
              className="h-full w-full object-cover"
              playsInline
              muted
              autoPlay
            />

            {/* Scanning overlay */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              {/* Dark overlay with cutout */}
              <div className="absolute inset-0 bg-black/50" />

              {/* Scanning area indicator */}
              <div className="relative w-[80%] max-w-[300px] aspect-[3/1]">
                {/* Clear area */}
                <div className="absolute inset-0 bg-transparent border-2 border-white/50 rounded-lg"
                     style={{ boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)' }} />

                {/* Corner indicators */}
                <div className="absolute top-0 left-0 w-6 h-6 border-t-4 border-l-4 border-primary-400 rounded-tl-lg" />
                <div className="absolute top-0 right-0 w-6 h-6 border-t-4 border-r-4 border-primary-400 rounded-tr-lg" />
                <div className="absolute bottom-0 left-0 w-6 h-6 border-b-4 border-l-4 border-primary-400 rounded-bl-lg" />
                <div className="absolute bottom-0 right-0 w-6 h-6 border-b-4 border-r-4 border-primary-400 rounded-br-lg" />

                {/* Scanning line animation */}
                {scanning && (
                  <div className="absolute left-2 right-2 h-0.5 bg-primary-400 animate-pulse"
                       style={{ top: '50%', boxShadow: '0 0 8px 2px rgba(59, 130, 246, 0.5)' }} />
                )}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer instructions */}
      <div className="absolute bottom-0 left-0 right-0 z-10 bg-gradient-to-t from-black/70 to-transparent p-6">
        <p className="text-white/80 text-center text-sm">
          Posicione o código de barras dentro da área marcada
        </p>
      </div>

      {/* Hidden canvas for processing */}
      <canvas ref={canvasRef} className="hidden" />
    </div>
  )
}
