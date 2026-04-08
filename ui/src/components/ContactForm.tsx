import { useState } from 'react'
import { postContact } from '../lib/api'

type FormState = 'idle' | 'submitting' | 'success' | 'error'

export default function ContactForm() {
  const [name,    setName]    = useState('')
  const [email,   setEmail]   = useState('')
  const [message, setMessage] = useState('')
  const [state,   setState]   = useState<FormState>('idle')
  const [err,     setErr]     = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !email.trim() || !message.trim()) return

    setState('submitting')
    try {
      await postContact({ name: name.trim(), email: email.trim(), message: message.trim() })
      setState('success')
    } catch (error) {
      setErr(error instanceof Error ? error.message : 'Something went wrong')
      setState('error')
    }
  }

  if (state === 'success') {
    return (
      <div className="contact-success">
        <div className="contact-success-icon">✓</div>
        <p>Got it. I'll be in touch.</p>
      </div>
    )
  }

  return (
    <form className="contact-form" onSubmit={handleSubmit}>
      <div className="contact-row">
        <div className="contact-field">
          <label htmlFor="cf-name">Name</label>
          <input
            id="cf-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="Your name"
            required
            disabled={state === 'submitting'}
          />
        </div>
        <div className="contact-field">
          <label htmlFor="cf-email">Email</label>
          <input
            id="cf-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@company.com"
            required
            disabled={state === 'submitting'}
          />
        </div>
      </div>

      <div className="contact-field">
        <label htmlFor="cf-message">What's on your mind?</label>
        <textarea
          id="cf-message"
          value={message}
          onChange={e => setMessage(e.target.value)}
          placeholder="Tell me where you're stuck, what you're trying to change, or just say hello."
          rows={4}
          required
          disabled={state === 'submitting'}
        />
      </div>

      {state === 'error' && (
        <p className="contact-error">{err}</p>
      )}

      <button type="submit" className="contact-submit" disabled={state === 'submitting'}>
        {state === 'submitting' ? 'Sending...' : 'Send message'}
      </button>
    </form>
  )
}
