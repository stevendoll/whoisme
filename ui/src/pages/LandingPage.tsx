import { useState } from 'react'
import { startAuth } from '../lib/api'

export default function LandingPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSignIn = async () => {
    const trimmed = email.trim()
    if (!trimmed) return
    setLoading(true)
    setError('')
    try {
      await startAuth(trimmed)
      setSent(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send link')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="landing-page">
      <div className="landing-content">
        <img src="/assets/whoisme-logo-transparent.png" alt="WhoIsMe" className="landing-logo" />
        <p className="landing-subheading">Your professional story, told in your voice.</p>
        <p className="landing-body">
          A short conversational interview that helps you articulate who you are, what you do,
          and what drives you. Answer a few questions and we'll craft a polished professional
          profile that sounds like you.
        </p>
        <a href="#/interview" className="btn-primary landing-start">
          Start interview
        </a>

        <div className="landing-divider"><span>or</span></div>

        <p className="landing-returning">Already have a profile? Sign in.</p>
        {!sent ? (
          <div className="landing-signin-row">
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSignIn()}
              placeholder="you@example.com"
              className="interview-text-input"
            />
            <button
              className="btn-ghost"
              onClick={handleSignIn}
              disabled={loading || !email.trim()}
            >
              {loading ? 'Sending…' : 'Sign in'}
            </button>
          </div>
        ) : (
          <p className="landing-auth-sent">Check your email — a sign-in link is on its way.</p>
        )}
        {error && <p className="interview-error">{error}</p>}
      </div>
    </div>
  )
}
