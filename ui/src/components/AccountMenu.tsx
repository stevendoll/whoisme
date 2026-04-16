import { useState, useEffect, useRef } from 'react'
import { getMe, createBearerToken, deleteAccount, unpublishProfile } from '../lib/api'
import type { UserProfile } from '../lib/types'

const API_URL = import.meta.env.VITE_API_URL ?? ''

function mcpUrl(username: string) {
  return `${API_URL}/users/profile/${username}`
}

async function copyToClipboard(text: string) {
  await navigator.clipboard.writeText(text)
}

export default function AccountMenu() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('whoisme_user_token'))
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState<string | null>(null)
  const [generatingToken, setGeneratingToken] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Keep login state in sync
  useEffect(() => {
    const sync = () => setIsLoggedIn(!!localStorage.getItem('whoisme_user_token'))
    window.addEventListener('storage', sync)
    const id = setInterval(sync, 500)
    return () => { window.removeEventListener('storage', sync); clearInterval(id) }
  }, [])

  // Load profile when logged in
  useEffect(() => {
    if (!isLoggedIn) { setProfile(null); return }
    getMe().then(setProfile).catch(() => {
      localStorage.removeItem('whoisme_user_token')
      setIsLoggedIn(false)
    })
  }, [isLoggedIn])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const flash = (key: string) => {
    setCopied(key)
    setTimeout(() => setCopied(null), 1800)
  }

  const handlePublicMcp = async () => {
    if (!profile?.username) return
    await copyToClipboard(mcpUrl(profile.username))
    flash('public')
  }

  const handlePrivateMcp = async () => {
    if (!profile?.username) return
    setGeneratingToken(true)
    try {
      const { token } = await createBearerToken()
      const url = mcpUrl(profile.username)
      await copyToClipboard(JSON.stringify({ url, headers: { Authorization: `Bearer ${token}` } }, null, 2))
      flash('private')
      setProfile(p => p ? { ...p, hasBearerToken: true } : p)
    } catch {
      // ignore
    } finally {
      setGeneratingToken(false)
    }
  }

  const handleDeleteProfile = async () => {
    if (!confirm('Delete your public profile and MCP server? This cannot be undone.')) return
    try {
      await unpublishProfile()
      setProfile(p => p ? { ...p, published: false, username: null } : p)
      setOpen(false)
    } catch { /* ignore */ }
  }

  const handleDeleteAccount = async () => {
    if (!confirm('Delete your account and all data permanently? This cannot be undone.')) return
    try {
      await deleteAccount()
      localStorage.removeItem('whoisme_session')
      localStorage.removeItem('whoisme_user_token')
      setOpen(false)
      history.replaceState(null, '', '#/')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    } catch { /* ignore */ }
  }

  const handleLogout = () => {
    localStorage.removeItem('whoisme_user_token')
    setIsLoggedIn(false)
    setProfile(null)
    setOpen(false)
    history.replaceState(null, '', '#/')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }

  const label = profile?.username ? profile.username : 'account'
  const active = isLoggedIn

  return (
    <div className="account-menu-wrap" ref={menuRef}>
      <button
        className={`account-btn${active ? ' account-btn--active' : ''}`}
        onClick={() => active && setOpen(v => !v)}
        disabled={!active}
        aria-haspopup="true"
        aria-expanded={open}
      >
        {label}
      </button>

      {open && (
        <div className="account-dropdown">
          {profile?.email && (
            <div className="account-dropdown-email">{profile.email}</div>
          )}

          {profile?.username && (
            <a
              href={`https://whoisme.io/u/${profile.username}`}
              target="_blank"
              rel="noopener noreferrer"
              className="account-dropdown-item"
              onClick={() => setOpen(false)}
            >
              card
            </a>
          )}

          {profile?.username && (
            <button className="account-dropdown-item" onClick={handlePublicMcp}>
              {copied === 'public' ? 'copied!' : 'public mcp link'}
            </button>
          )}

          {profile?.username && (
            <button className="account-dropdown-item" onClick={handlePrivateMcp} disabled={generatingToken}>
              {generatingToken ? 'generating…' : copied === 'private' ? 'copied!' : 'private mcp link'}
            </button>
          )}

          {profile?.username && (
            <button className="account-dropdown-item account-dropdown-item--danger" onClick={handleDeleteProfile}>
              delete profile &amp; mcp server
            </button>
          )}

          <button className="account-dropdown-item account-dropdown-item--danger" onClick={handleDeleteAccount}>
            delete account
          </button>

          <button className="account-dropdown-item" onClick={handleLogout}>
            log out
          </button>
        </div>
      )}
    </div>
  )
}
