import { useEffect, useRef } from 'react'

// Only show custom cursor on pointer/mouse devices
const isTouch = typeof window !== 'undefined' &&
  window.matchMedia('(hover: none) and (pointer: coarse)').matches

export default function Cursor() {
  const dotRef = useRef<HTMLDivElement>(null)
  const ringRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isTouch) return

    let mx = 0, my = 0, rx = 0, ry = 0
    const rafId = { current: 0 }

    const onMove = (e: MouseEvent) => {
      mx = e.clientX
      my = e.clientY
      if (dotRef.current) {
        dotRef.current.style.left = mx + 'px'
        dotRef.current.style.top = my + 'px'
      }
    }

    const animateRing = () => {
      rx += (mx - rx) * 0.12
      ry += (my - ry) * 0.12
      if (ringRef.current) {
        ringRef.current.style.left = rx + 'px'
        ringRef.current.style.top = ry + 'px'
      }
      rafId.current = requestAnimationFrame(animateRing)
    }

    document.addEventListener('mousemove', onMove)
    rafId.current = requestAnimationFrame(animateRing)

    return () => {
      document.removeEventListener('mousemove', onMove)
      cancelAnimationFrame(rafId.current)
    }
  }, [])

  if (isTouch) return null

  return (
    <>
      <div ref={dotRef} style={{ position: 'fixed', width: 10, height: 10, background: 'var(--accent)', borderRadius: '50%', pointerEvents: 'none', zIndex: 9999, transform: 'translate(-50%,-50%)' }} />
      <div ref={ringRef} style={{ position: 'fixed', width: 36, height: 36, border: '1px solid rgba(77,182,172,0.4)', borderRadius: '50%', pointerEvents: 'none', zIndex: 9998, transform: 'translate(-50%,-50%)' }} />
    </>
  )
}
