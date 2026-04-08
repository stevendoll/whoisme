import { useState, useEffect } from 'react'

interface HeckleToastProps {
  text: string | null
}

export default function HeckleToast({ text }: HeckleToastProps) {
  const [visible, setVisible] = useState(false)
  const [current, setCurrent] = useState<string | null>(null)

  useEffect(() => {
    if (!text) return
    setCurrent(text)
    setVisible(true)
  }, [text])

  if (!visible || !current) return null

  return (
    <div className="heckle-toast" role="status" aria-live="polite">
      <span className="heckle-label">peanut gallery</span>
      <span className="heckle-text">{current}</span>
      <button
        className="heckle-dismiss"
        onClick={() => setVisible(false)}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  )
}
