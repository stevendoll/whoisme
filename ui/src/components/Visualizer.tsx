import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react'

export interface VisualizerHandle {
  start(analyser: AnalyserNode): void
  stop(): void
}

const Visualizer = forwardRef<VisualizerHandle>((_, ref) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const rafRef = useRef<number>(0)

  useImperativeHandle(ref, () => ({
    start(analyser: AnalyserNode) {
      const canvas = canvasRef.current
      if (!canvas) return
      canvas.style.opacity = '1'
      const ctx = canvas.getContext('2d')!
      const buf = new Uint8Array(analyser.frequencyBinCount)

      const draw = () => {
        rafRef.current = requestAnimationFrame(draw)
        analyser.getByteFrequencyData(buf)
        const W = canvas.width, H = canvas.height
        ctx.clearRect(0, 0, W, H)
        const barW = (W / buf.length) * 2.2
        let x = 0
        for (let i = 0; i < buf.length; i++) {
          const ratio = buf[i] / 255
          const barH = ratio * H
          const alpha = 0.15 + ratio * 0.85
          ctx.fillStyle = `rgba(77,182,172,${alpha})`
          ctx.fillRect(x, H - barH, barW - 1, barH)
          x += barW
        }
      }
      draw()
    },
    stop() {
      cancelAnimationFrame(rafRef.current)
      const canvas = canvasRef.current
      if (!canvas) return
      canvas.getContext('2d')!.clearRect(0, 0, canvas.width, canvas.height)
      canvas.style.opacity = '0'
    },
  }))

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ro = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth
      canvas.height = canvas.offsetHeight
    })
    ro.observe(canvas)
    return () => ro.disconnect()
  }, [])

  return <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '56px', opacity: 0, transition: 'opacity 0.4s' }} />
})

Visualizer.displayName = 'Visualizer'
export default Visualizer
