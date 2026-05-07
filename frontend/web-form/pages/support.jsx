import Link from 'next/link';
import SupportForm from '../SupportForm';

const perks = [
  { icon: '⚡', title: 'Under 5 minutes', desc: 'AI responds instantly — even at 3 AM.' },
  { icon: '🧠', title: 'Urooj Waheed AI', desc: 'Smart, empathetic, context-aware replies.' },
  { icon: '🔀', title: 'Auto Escalation', desc: 'Complex issues routed to humans with full context.' },
  { icon: '🎫', title: 'Ticket Tracking', desc: 'Real-time status updates on your request.' },
];

export default function SupportPage() {
  return (
    <div style={{ minHeight: '100vh', background: '#07070f', position: 'relative', overflow: 'hidden' }}>
      {/* Orbs */}
      <div style={{ position: 'fixed', top: 0, left: 0, width: 500, height: 500, borderRadius: '50%',
        background: '#4f46e5', filter: 'blur(120px)', opacity: 0.08, pointerEvents: 'none' }} />
      <div style={{ position: 'fixed', bottom: 0, right: 0, width: 400, height: 400, borderRadius: '50%',
        background: '#7c3aed', filter: 'blur(120px)', opacity: 0.08, pointerEvents: 'none' }} />

      {/* Dot grid */}
      <div style={{ position: 'fixed', inset: 0, opacity: 0.3, pointerEvents: 'none',
        backgroundImage: 'radial-gradient(circle, rgba(99,102,241,0.12) 1px, transparent 1px)',
        backgroundSize: '28px 28px' }} />

      {/* Topbar */}
      <header style={{ position: 'sticky', top: 0, zIndex: 100,
        background: 'rgba(7,7,15,0.85)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '0 24px', height: 60,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, background: 'linear-gradient(135deg,#4f46e5,#7c3aed)',
              display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
              </svg>
            </div>
            <span style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 16 }}>FlowForge</span>
          </Link>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#64748b',
            fontSize: 14, textDecoration: 'none', transition: 'color 0.2s' }}
            onMouseOver={e=>e.currentTarget.style.color='#f1f5f9'}
            onMouseOut={e=>e.currentTarget.style.color='#64748b'}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 5 5 12 12 19"/>
            </svg>
            Back to Home
          </Link>
        </div>
      </header>

      {/* Body */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '56px 24px',
        display: 'grid', gridTemplateColumns: '340px 1fr', gap: 48, alignItems: 'start',
        position: 'relative' }}>

        {/* ── Left sidebar ── */}
        <aside>
          <div style={{ marginBottom: 36 }}>
            <span className="section-label">Support</span>
            <h1 style={{ fontSize: 36, fontWeight: 900, letterSpacing: '-0.03em', color: '#f8fafc',
              marginTop: 16, marginBottom: 14, lineHeight: 1.15 }}>
              How can we<br /><span className="g-text">help you?</span>
            </h1>
            <p style={{ fontSize: 15, color: '#64748b', lineHeight: 1.7 }}>
              Our Urooj Waheed AI agent reads your message, searches the knowledge base, and sends a personalized reply in minutes.
            </p>
          </div>

          {/* Perks */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 32 }}>
            {perks.map(p => (
              <div key={p.title} className="card-lift" style={{ display: 'flex', alignItems: 'flex-start', gap: 14,
                padding: '16px 18px', borderRadius: 14, background: 'rgba(255,255,255,0.02)',
                border: '1px solid rgba(255,255,255,0.06)', cursor: 'default' }}>
                <span style={{ fontSize: 20, flexShrink: 0 }}>{p.icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14, color: '#f1f5f9', marginBottom: 3 }}>{p.title}</div>
                  <div style={{ fontSize: 13, color: '#64748b', lineHeight: 1.5 }}>{p.desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Status indicator */}
          <div style={{ padding: '18px 20px', borderRadius: 14, background: 'rgba(74,222,128,0.04)',
            border: '1px solid rgba(74,222,128,0.15)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
              <span className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%',
                background: '#4ade80', display: 'inline-block' }} />
              <span style={{ fontWeight: 600, fontSize: 14, color: '#4ade80' }}>All Systems Operational</span>
            </div>
            {['AI Agent','Web Form','Ticket System'].map(s => (
              <div key={s} style={{ display: 'flex', justifyContent: 'space-between',
                fontSize: 13, marginBottom: 6 }}>
                <span style={{ color: '#64748b' }}>{s}</span>
                <span style={{ color: '#4ade80' }}>● Online</span>
              </div>
            ))}
          </div>
        </aside>

        {/* ── Right: Form ── */}
        <div className="card-lift" style={{ borderRadius: 24, overflow: 'hidden',
          background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.07)',
          boxShadow: '0 32px 64px rgba(0,0,0,0.4)' }}>
          {/* Form header bar */}
          <div style={{ padding: '24px 28px', borderBottom: '1px solid rgba(255,255,255,0.06)',
            background: 'rgba(99,102,241,0.04)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: '#f1f5f9', marginBottom: 3 }}>Submit a Ticket</h2>
              <p style={{ fontSize: 13, color: '#64748b' }}>We'll reply via AI in under 5 minutes.</p>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {['#ef4444','#f59e0b','#22c55e'].map(c => (
                <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c, opacity: 0.6 }} />
              ))}
            </div>
          </div>

          {/* Form */}
          <div className="dark-form">
            <SupportForm
              apiEndpoint={process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/channels/web-form/submit'}
              companyName="FlowForge"
            />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer style={{ borderTop: '1px solid rgba(255,255,255,.05)', marginTop: 40 }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', padding: '36px 24px',
          display: 'grid', gridTemplateColumns: '1fr auto auto', gap: 40, alignItems: 'start',
          flexWrap: 'wrap' }}>

          {/* Brand + tagline */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <div style={{ width: 26, height: 26, borderRadius: 7,
                background: 'linear-gradient(135deg,#4f46e5,#7c3aed)',
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                </svg>
              </div>
              <span style={{ color: '#f1f5f9', fontWeight: 700, fontSize: 15 }}>FlowForge</span>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#818cf8',
                background: 'rgba(99,102,241,.12)', border: '1px solid rgba(99,102,241,.25)',
                padding: '2px 7px', borderRadius: 99, textTransform: 'uppercase', letterSpacing: '.06em' }}>AI</span>
            </div>
            <p style={{ fontSize: 12, color: '#334155', lineHeight: 1.7, maxWidth: 280 }}>
              AI-powered support across Gmail, WhatsApp, and Web Form. Available 24/7 — tickets resolved in minutes.
            </p>
            <div style={{ marginTop: 14, fontSize: 11, color: '#1e293b' }}>
              © {new Date().getFullYear()} FlowForge · Built by{' '}
              <span style={{ color: '#6366f1', fontWeight: 600 }}>Urooj Waheed</span>
            </div>
          </div>

          {/* Quick links */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#6366f1', letterSpacing: '.1em',
              textTransform: 'uppercase', marginBottom: 12 }}>Quick Links</div>
            {[['← Back to Home','/'],['Submit Ticket','/support'],['Track Status','/support']].map(([label, href]) => (
              <a key={label} href={href} style={{ display: 'block', color: '#475569', fontSize: 13,
                textDecoration: 'none', marginBottom: 8, transition: 'color .2s' }}
                onMouseOver={e=>e.target.style.color='#f1f5f9'}
                onMouseOut={e=>e.target.style.color='#475569'}>{label}</a>
            ))}
          </div>

          {/* Built by card */}
          <div style={{ padding: '16px 18px', borderRadius: 14,
            background: 'rgba(99,102,241,.05)', border: '1px solid rgba(99,102,241,.12)',
            minWidth: 180 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#a855f7', letterSpacing: '.1em',
              textTransform: 'uppercase', marginBottom: 10 }}>Built By</div>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', marginBottom: 3 }}>Urooj Waheed</div>
            <div style={{ fontSize: 11, color: '#475569', lineHeight: 1.6, marginBottom: 10 }}>
              AI Engineer<br/>FlowForge Customer Success
            </div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 99,
              background: 'rgba(74,222,128,.06)', border: '1px solid rgba(74,222,128,.2)' }}>
              <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#4ade80', display: 'inline-block' }} />
              <span style={{ fontSize: 10, color: '#4ade80', fontWeight: 600 }}>Online</span>
            </div>
          </div>
        </div>

        {/* Bottom strip */}
        <div style={{ borderTop: '1px solid rgba(255,255,255,.03)', padding: '14px 24px',
          textAlign: 'center', fontSize: 11, color: '#1e293b' }}>
          FlowForge AI Support · Powered by <span style={{ color: '#6366f1' }}>Urooj Waheed</span>
        </div>
      </footer>
    </div>
  );
}
