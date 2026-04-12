import Nav from '../components/Nav'

export default function AdminPage() {
  return (
    <>
      <Nav />
      <div className="history-page">
        <div style={{ maxWidth: 720, margin: '0 auto', padding: '2rem 1.5rem' }}>
          <h2 style={{ fontSize: '1.1rem', letterSpacing: '0.05em', color: 'var(--accent)' }}>Admin</h2>
          <p style={{ color: 'rgba(240,242,255,0.4)', fontSize: '0.9rem' }}>Nothing to manage here yet.</p>
        </div>
      </div>
    </>
  )
}
