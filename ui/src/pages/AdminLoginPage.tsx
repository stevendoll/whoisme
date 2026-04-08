import { useState } from 'react'
import { postAdminLogin } from '../lib/api'
import Nav from '../components/Nav'

export default function AdminLoginPage() {
  const [email,     setEmail]     = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')

  const handleSubmit = async () => {
    const e = email.trim()
    if (!e) return
    setLoading(true)
    setError('')
    try {
      await postAdminLogin(e)
      setSubmitted(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Nav />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', padding: '2rem' }}>
        <div style={{ width: '100%', maxWidth: 360 }}>
          {submitted ? (
            <div style={{ textAlign: 'center' }}>
              <p style={{ color: 'var(--accent)', marginBottom: '0.5rem', fontSize: '1rem' }}>Check your email</p>
              <p style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.85rem' }}>
                If that address is authorised, a link is on its way. It expires in 1 hour.
              </p>
            </div>
          ) : (
            <>
              <p style={{ color: 'rgba(245,240,232,0.5)', fontSize: '0.85rem', marginBottom: '1.25rem', textAlign: 'center' }}>
                Enter your email to receive a sign-in link.
              </p>

              {error && (
                <p style={{ color: '#ff6b6b', fontSize: '0.8rem', marginBottom: '0.75rem', textAlign: 'center' }}>{error}</p>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <input
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') void handleSubmit() }}
                  placeholder="you@example.com"
                  autoFocus
                  style={{
                    background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
                    borderRadius: 6, padding: '0.6rem 0.75rem', color: 'var(--fg)',
                    fontSize: '0.9rem', outline: 'none', width: '100%', boxSizing: 'border-box',
                  }}
                />
                <button
                  onClick={() => void handleSubmit()}
                  disabled={loading || !email.trim()}
                  style={{
                    background: 'var(--accent)', color: '#000', border: 'none', borderRadius: 6,
                    padding: '0.6rem', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer',
                    opacity: loading || !email.trim() ? 0.5 : 1,
                  }}
                >
                  {loading ? '...' : 'Send link'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
