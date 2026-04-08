import { useState, useEffect } from 'react'
import Cursor from './components/Cursor'
import Home from './pages/Home'
import HistoryPage from './pages/HistoryPage'
import AdminPage from './pages/AdminPage'
import AdminLoginPage from './pages/AdminLoginPage'
import InterviewPage from './pages/InterviewPage'
import { postAdminVerify, verifyAuth } from './lib/api'

const STORAGE_KEY = 'whoisme_admin'
const USER_TOKEN_KEY = 'whoisme_user_token'

function useHashRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const handler = () => setHash(window.location.hash)
    window.addEventListener('hashchange', handler)
    return () => window.removeEventListener('hashchange', handler)
  }, [])
  return hash
}

export default function App() {
  const hash     = useHashRoute()
  const basePath = hash.split('?')[0]

  const [adminAuthed, setAdminAuthed] = useState(() => !!localStorage.getItem(STORAGE_KEY))

  // On mount: if /#/admin?token=... is present, verify admin
  useEffect(() => {
    if (!basePath.startsWith('#/admin')) return
    if (adminAuthed) return

    const qIdx = hash.indexOf('?')
    if (qIdx === -1) return
    const token = new URLSearchParams(hash.slice(qIdx + 1)).get('token')
    if (!token) return

    postAdminVerify(token).then(r => {
      if (r.ok && r.email) {
        localStorage.setItem(STORAGE_KEY, r.email)
        setAdminAuthed(true)
        history.replaceState(null, '', '#/admin')
      }
    }).catch(() => { /* invalid token — stay on login page */ })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // On mount: if /#/verify?token=... is present, verify user magic link
  useEffect(() => {
    if (basePath !== '#/verify') return

    const qIdx = hash.indexOf('?')
    if (qIdx === -1) return
    const token = new URLSearchParams(hash.slice(qIdx + 1)).get('token')
    if (!token) return

    verifyAuth(token).then(r => {
      localStorage.setItem(USER_TOKEN_KEY, r.token)
      history.replaceState(null, '', '#/interview')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    }).catch(() => {
      history.replaceState(null, '', '#/interview')
      window.dispatchEvent(new HashChangeEvent('hashchange'))
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const page = basePath === '#/history'              ? 'history'
             : basePath === '#/interview'             ? 'interview'
             : basePath === '#/verify'               ? 'interview'
             : basePath === '#/admin' && adminAuthed ? 'admin'
             : basePath === '#/admin'                ? 'admin-login'
             : 'home'

  return (
    <>
      <Cursor />
      <div className="fixed inset-0 pointer-events-none z-0 bg-[image:linear-gradient(var(--border)_1px,transparent_1px),linear-gradient(90deg,var(--border)_1px,transparent_1px)] bg-[size:80px_80px] [mask-image:radial-gradient(ellipse_at_center,transparent_30%,black_100%)]" />
      {page === 'history'    ? <HistoryPage />
     : page === 'interview'  ? <InterviewPage />
     : page === 'admin'      ? <AdminPage />
     : page === 'admin-login'? <AdminLoginPage />
     : <Home />}
    </>
  )
}
