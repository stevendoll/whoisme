import { useState, useEffect, useRef } from 'react'
import {
  getAdminIcebreakers,
  createIcebreaker,
  updateIcebreaker,
  deleteIcebreaker,
} from '../lib/api'
import type { AdminIcebreaker } from '../lib/types'
import Nav from '../components/Nav'

export default function AdminPage() {
  const [items,    setItems]    = useState<AdminIcebreaker[]>([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [newText,  setNewText]  = useState('')
  const [adding,   setAdding]   = useState(false)
  const [editId,   setEditId]   = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const editRef = useRef<HTMLInputElement>(null)

  const load = () => {
    setLoading(true)
    getAdminIcebreakers()
      .then(r => setItems(r.items))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  useEffect(() => {
    if (editId) editRef.current?.focus()
  }, [editId])

  const handleAdd = async () => {
    const text = newText.trim()
    if (!text) return
    setAdding(true)
    try {
      const item = await createIcebreaker(text)
      setItems(prev => [item, ...prev])
      setNewText('')
    } catch (e) {
      setError(String(e))
    } finally {
      setAdding(false)
    }
  }

  const handleToggle = async (item: AdminIcebreaker) => {
    const next = item.isActive === 'false' ? 'true' : 'false'
    setItems(prev => prev.map(i => i.id === item.id ? { ...i, isActive: next } : i))
    try {
      await updateIcebreaker(item.id, { is_active: next })
    } catch (e) {
      setError(String(e))
      load()
    }
  }

  const startEdit = (item: AdminIcebreaker) => {
    setEditId(item.id)
    setEditText(item.text)
  }

  const saveEdit = async (id: string) => {
    const text = editText.trim()
    if (!text) { setEditId(null); return }
    setItems(prev => prev.map(i => i.id === id ? { ...i, text } : i))
    setEditId(null)
    try {
      await updateIcebreaker(id, { text })
    } catch (e) {
      setError(String(e))
      load()
    }
  }

  const handleDelete = async (id: string) => {
    setItems(prev => prev.filter(i => i.id !== id))
    try {
      await deleteIcebreaker(id)
    } catch (e) {
      setError(String(e))
      load()
    }
  }

  return (
    <>
      <Nav />
      <div className="history-page">
        <div style={{ maxWidth: 720, margin: '0 auto', padding: '2rem 1.5rem', width: '100%' }}>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.1rem', letterSpacing: '0.05em', color: 'var(--accent)' }}>
              Icebreakers
            </h2>
            <a href="#" style={{ fontSize: '0.8rem', color: 'rgba(245,240,232,0.4)', textDecoration: 'none' }}>
              ← Back
            </a>
          </div>

          {error && (
            <p style={{ color: '#ff6b6b', fontSize: '0.85rem', marginBottom: '1rem' }}>{error}</p>
          )}

          {/* Add new */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem' }}>
            <input
              type="text"
              value={newText}
              onChange={e => setNewText(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') void handleAdd() }}
              placeholder="New icebreaker text..."
              style={{
                flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '0.5rem 0.75rem', color: 'var(--fg)',
                fontSize: '0.9rem', outline: 'none',
              }}
            />
            <button
              onClick={() => void handleAdd()}
              disabled={adding || !newText.trim()}
              style={{
                background: 'var(--accent)', color: '#000', border: 'none', borderRadius: 6,
                padding: '0.5rem 1rem', fontSize: '0.85rem', cursor: 'pointer', fontWeight: 600,
                opacity: adding || !newText.trim() ? 0.5 : 1,
              }}
            >
              {adding ? '...' : 'Add'}
            </button>
          </div>

          {/* List */}
          {loading && <p style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.9rem' }}>Loading...</p>}

          {!loading && items.length === 0 && (
            <p style={{ color: 'rgba(245,240,232,0.4)', fontSize: '0.9rem' }}>No icebreakers yet.</p>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {items.map(item => {
              const active = item.isActive !== 'false'
              return (
                <div
                  key={item.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.75rem',
                    background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)',
                    borderRadius: 8, padding: '0.6rem 0.75rem',
                    opacity: active ? 1 : 0.45,
                  }}
                >
                  {/* Active toggle */}
                  <button
                    onClick={() => void handleToggle(item)}
                    title={active ? 'Deactivate' : 'Activate'}
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: active ? 'var(--accent)' : 'rgba(245,240,232,0.3)',
                      fontSize: '1rem', padding: 0, lineHeight: 1, flexShrink: 0,
                    }}
                  >
                    {active ? '●' : '○'}
                  </button>

                  {/* Text / edit */}
                  {editId === item.id ? (
                    <input
                      ref={editRef}
                      type="text"
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter')  void saveEdit(item.id)
                        if (e.key === 'Escape') setEditId(null)
                      }}
                      onBlur={() => void saveEdit(item.id)}
                      style={{
                        flex: 1, background: 'transparent', border: 'none', borderBottom: '1px solid var(--accent)',
                        color: 'var(--fg)', fontSize: '0.9rem', outline: 'none', padding: '0.1rem 0',
                      }}
                    />
                  ) : (
                    <span
                      onClick={() => startEdit(item)}
                      style={{ flex: 1, fontSize: '0.9rem', cursor: 'text', color: 'var(--fg)', lineHeight: 1.4 }}
                    >
                      {item.text}
                    </span>
                  )}

                  {/* Delete */}
                  <button
                    onClick={() => void handleDelete(item.id)}
                    title="Delete"
                    style={{
                      background: 'none', border: 'none', cursor: 'pointer',
                      color: 'rgba(245,240,232,0.25)', fontSize: '0.9rem', padding: 0,
                      lineHeight: 1, flexShrink: 0,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#ff6b6b')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(245,240,232,0.25)')}
                  >
                    ✕
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </>
  )
}
