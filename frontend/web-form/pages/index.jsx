import dynamic from 'next/dynamic';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

// Load Three.js only on client (no SSR)
const Scene3D = dynamic(() => import('../components/Scene3D'), { ssr: false });

/* ── Counter ─────────────────────────────────────────────── */
function Counter({ to, suffix = '' }) {
  const [n, setN] = useState(0);
  const r = useRef(null);
  useEffect(() => {
    const ob = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      ob.disconnect();
      let i = 0; const steps = 60;
      const id = setInterval(() => {
        i++; setN(Math.round(to * (i / steps)));
        if (i >= steps) clearInterval(id);
      }, 1600 / steps);
    }, { threshold: 0.5 });
    if (r.current) ob.observe(r.current);
    return () => ob.disconnect();
  }, [to]);
  return <span ref={r}>{n.toLocaleString()}{suffix}</span>;
}

/* ── Navbar ──────────────────────────────────────────────── */
function Nav() {
  const [sc, setSc] = useState(false);
  useEffect(() => {
    const fn = () => setSc(window.scrollY > 40);
    window.addEventListener('scroll', fn, { passive: true });
    return () => window.removeEventListener('scroll', fn);
  }, []);
  return (
    <header style={{
      position: 'fixed', top: 0, inset: 'auto 0 auto 0', zIndex: 200,
      background: sc ? 'rgba(7,7,15,0.97)' : 'transparent',
      borderBottom: sc ? '1px solid rgba(255,255,255,0.07)' : 'none',
      transition: 'all .3s',
    }}>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '0 28px', height: 66,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg,#4f46e5,#a855f7)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 24px rgba(79,70,229,.6)' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </div>
          <span style={{ color: '#f8fafc', fontWeight: 800, fontSize: 18, letterSpacing: '-.02em' }}>FlowForge</span>
          <span style={{ fontSize: 10, fontWeight: 700, color: '#818cf8', letterSpacing: '.08em',
            background: 'rgba(99,102,241,.12)', border: '1px solid rgba(99,102,241,.25)',
            padding: '2px 8px', borderRadius: 99, textTransform: 'uppercase' }}>AI</span>
        </div>

        <nav style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
          {['Features','Channels','How It Works'].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(/ /g,'-')}`}
              style={{ color: '#94a3b8', fontSize: 14, fontWeight: 500, textDecoration: 'none', transition: 'color .2s' }}
              onMouseOver={e=>e.target.style.color='#f8fafc'}
              onMouseOut={e=>e.target.style.color='#94a3b8'}>{l}</a>
          ))}
          <Link href="/support" className="btn-primary" style={{ padding: '10px 22px', fontSize: 14, borderRadius: 11 }}>
            Get Support →
          </Link>
        </nav>
      </div>
    </header>
  );
}

/* ── HERO with 3D ────────────────────────────────────────── */
function Hero() {
  return (
    <section style={{ position: 'relative', height: '100vh', minHeight: 680,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      overflow: 'hidden', background: '#07070f' }}>

      {/* Three.js Canvas fills entire hero */}
      <Scene3D />

      {/* Dark vignette edges */}
      <div style={{ position: 'absolute', inset: 0, background:
        'radial-gradient(ellipse 80% 70% at 50% 50%, transparent 30%, rgba(7,7,15,.85) 100%)',
        pointerEvents: 'none', zIndex: 1 }} />

      {/* Bottom fade into next section */}
      <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 180,
        background: 'linear-gradient(to bottom, transparent, #07070f)',
        pointerEvents: 'none', zIndex: 2 }} />

      {/* Text overlay */}
      <div style={{ position: 'relative', zIndex: 10, textAlign: 'center',
        padding: '0 24px', maxWidth: 760 }}>

        <div className="slide-up" style={{ display: 'inline-flex', alignItems: 'center', gap: 8,
          padding: '6px 18px', borderRadius: 99, marginBottom: 30,
          background: 'rgba(99,102,241,.1)', border: '1px solid rgba(99,102,241,.3)',
          backdropFilter: 'blur(8px)' }}>
          <span className="pulse-dot" style={{ width: 7, height: 7, borderRadius: '50%',
            background: '#4ade80', display: 'inline-block' }} />
          <span style={{ fontSize: 13, color: '#a5b4fc', fontWeight: 500 }}>
            Urooj Waheed · Live AI Support · 24/7
          </span>
        </div>

        <h1 className="slide-up delay-1" style={{
          fontSize: 'clamp(44px, 8vw, 90px)', fontWeight: 900,
          letterSpacing: '-.045em', lineHeight: 1.0, color: '#f8fafc', marginBottom: 24,
          textShadow: '0 0 80px rgba(99,102,241,.4)',
        }}>
          Customer Support<br />
          <span className="g-text" style={{ fontSize: '105%' }}>Reimagined with AI</span>
        </h1>

        <p className="slide-up delay-2" style={{ fontSize: 18, color: '#94a3b8', lineHeight: 1.75,
          marginBottom: 44, maxWidth: 520, margin: '0 auto 44px',
          textShadow: '0 2px 20px rgba(0,0,0,.8)' }}>
          One AI agent. Three channels.{' '}
          <strong style={{ color: '#fca5a5' }}>Gmail</strong>,{' '}
          <strong style={{ color: '#86efac' }}>WhatsApp</strong>,{' '}
          <strong style={{ color: '#93c5fd' }}>Web Form</strong>.{' '}
          Tickets resolved in under 5 minutes — automatically.
        </p>

        <div className="slide-up delay-3" style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Link href="/support" className="btn-primary" style={{ fontSize: 16, padding: '14px 32px' }}>
            Submit a Ticket
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
            </svg>
          </Link>
          <a href="#features" className="btn-ghost" style={{ fontSize: 16, padding: '14px 32px',
            backdropFilter: 'blur(12px)', background: 'rgba(255,255,255,0.06)' }}>
            Explore Features
          </a>
        </div>

        {/* Move mouse hint */}
        <p className="slide-up delay-4" style={{ marginTop: 40, fontSize: 12, color: '#334155',
          letterSpacing: '.06em', textTransform: 'uppercase' }}>
          ↕ Move mouse to interact with the 3D scene
        </p>
      </div>

      {/* Scroll cue */}
      <div style={{ position: 'absolute', bottom: 36, left: '50%', transform: 'translateX(-50%)',
        zIndex: 10, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 11, color: '#334155', letterSpacing: '.08em', textTransform: 'uppercase' }}>Scroll</span>
        <div style={{ width: 22, height: 36, borderRadius: 11, border: '1px solid rgba(255,255,255,.1)',
          display: 'flex', justifyContent: 'center', paddingTop: 6 }}>
          <div style={{ width: 3, height: 8, borderRadius: 99, background: '#6366f1',
            animation: 'f1 1.6s ease-in-out infinite' }} />
        </div>
      </div>
    </section>
  );
}

/* ── Stats ───────────────────────────────────────────────── */
function Stats() {
  const items = [
    { v: 98, s: '%', l: 'Resolution Rate', icon: '🎯' },
    { v: 5,  s: 'min', l: 'Avg Response', icon: '⚡' },
    { v: 10000, s: '+', l: 'Tickets Handled', icon: '🎫' },
    { v: 99, s: '.9%', l: 'Uptime', icon: '🌍' },
  ];
  return (
    <section style={{ padding: '80px 24px', borderTop: '1px solid rgba(255,255,255,.05)',
      borderBottom: '1px solid rgba(255,255,255,.05)', background: '#07070f' }}>
      <div style={{ maxWidth: 900, margin: '0 auto',
        display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 20 }}>
        {items.map((it, i) => (
          <div key={i} className="card-lift shimmer" style={{ textAlign: 'center', padding: '32px 16px',
            borderRadius: 18, background: 'rgba(255,255,255,.02)',
            border: '1px solid rgba(255,255,255,.06)', cursor: 'default' }}>
            <div style={{ fontSize: 28, marginBottom: 10 }}>{it.icon}</div>
            <div style={{ fontSize: 42, fontWeight: 900, letterSpacing: '-.04em', lineHeight: 1 }}>
              <span className="g-text">
                {it.v === 10000
                  ? <Counter to={10000} suffix="+" />
                  : it.v === 99
                  ? <><Counter to={99} />{it.s}</>
                  : <><Counter to={it.v} />{it.s}</>}
              </span>
            </div>
            <div style={{ fontSize: 13, color: '#475569', marginTop: 10, fontWeight: 500 }}>{it.l}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

/* ── Features ────────────────────────────────────────────── */
function Features() {
  const list = [
    { icon: '🧠', t: 'Urooj Waheed AI Engine', d: 'State-of-the-art reasoning generates accurate, empathetic responses. Context-aware, multi-turn conversations.', tags: ['NLP','Tool use','Context'] },
    { icon: '📚', t: 'Semantic Knowledge Search', d: 'pgvector cosine similarity finds the perfect answer from your docs in milliseconds using OpenAI embeddings.', tags: ['RAG','pgvector','Semantic'] },
    { icon: '🔀', t: 'Smart Escalation Engine', d: 'Detects frustration via sentiment analysis. Auto-routes complex issues to humans with full conversation context.', tags: ['Sentiment','Auto-route','Priority'] },
    { icon: '🎫', t: 'Full Ticket Lifecycle', d: 'Every message becomes a tracked ticket. Cross-channel identity resolution. PostgreSQL backed.', tags: ['PostgreSQL','History','Identity'] },
    { icon: '⚡', t: 'Multi-Channel in Real-time', d: 'One AI brain across Gmail, WhatsApp and Web Form. Context preserved when customers switch channels.', tags: ['Gmail','WhatsApp','Form'] },
    { icon: '📊', t: 'Analytics & Metrics', d: 'Resolution rates, escalation trends, and sentiment scores broken down by channel in real-time.', tags: ['Metrics','Trends','Reports'] },
  ];
  return (
    <section id="features" style={{ padding: '110px 24px', background: '#07070f' }}>
      <div style={{ maxWidth: 1100, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 70 }}>
          <span className="section-label">Features</span>
          <h2 style={{ fontSize: 'clamp(34px,5vw,56px)', fontWeight: 900, letterSpacing: '-.03em',
            color: '#f8fafc', marginTop: 20, marginBottom: 18 }}>
            Everything to <span className="g-text">delight customers</span>
          </h2>
          <p style={{ fontSize: 17, color: '#475569', maxWidth: 440, margin: '0 auto' }}>
            A full-stack AI support system — built for scale, speed and reliability.
          </p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 18 }}>
          {list.map((f, i) => (
            <div key={i} className="card-lift glow-card shimmer" style={{ borderRadius: 20, padding: 30,
              background: 'rgba(255,255,255,.02)', cursor: 'default' }}>
              <div style={{ fontSize: 30, marginBottom: 18, width: 56, height: 56, borderRadius: 14,
                background: 'rgba(99,102,241,.1)', border: '1px solid rgba(99,102,241,.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{f.icon}</div>
              <h3 style={{ fontSize: 17, fontWeight: 700, color: '#f1f5f9', marginBottom: 10 }}>{f.t}</h3>
              <p style={{ fontSize: 14, color: '#475569', lineHeight: 1.75, marginBottom: 18 }}>{f.d}</p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {f.tags.map(t => <span key={t} className="chip">{t}</span>)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Channels ────────────────────────────────────────────── */
function Channels() {
  const [active, setActive] = useState(0);
  const channels = [
    {
      tab: '📧 Gmail', title: 'Gmail / Email Channel', color: '#ef4444', glow: 'rgba(239,68,68,.12)',
      desc: 'Automatically monitors your support inbox via Gmail OAuth and Google Pub/Sub. Every email creates a tracked ticket and gets an AI-drafted reply within minutes.',
      points: ['OAuth2 secure authentication', 'Google Pub/Sub real-time webhooks', 'Thread-aware replies', 'HTML & attachment support'],
      badge: { label: 'Production', color: '#ef4444' },
    },
    {
      tab: '💬 WhatsApp', title: 'WhatsApp Business Channel', color: '#22c55e', glow: 'rgba(34,197,94,.12)',
      desc: 'Connected to Meta Cloud API v20.0. One active conversation per phone number — instant AI replies, no waiting in queues.',
      points: ['Meta Cloud API v20.0', 'Webhook verify + message handler', 'Single session per phone', 'Media message support'],
      badge: { label: 'Live', color: '#22c55e' },
    },
    {
      tab: '🌐 Web Form', title: 'Embeddable Web Form', color: '#6366f1', glow: 'rgba(99,102,241,.12)',
      desc: 'Drop-in React widget for any website. Synchronous AI response shown instantly after submission — customers see answers in seconds.',
      points: ['Embeddable React component', 'Client-side validation', 'Synchronous AI response', 'Ticket status polling'],
      badge: { label: 'This Page', color: '#6366f1' },
    },
  ];
  const ch = channels[active];
  return (
    <section id="channels" style={{ padding: '110px 24px', background: 'rgba(255,255,255,.01)' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 60 }}>
          <span className="section-label">Channels</span>
          <h2 style={{ fontSize: 'clamp(34px,5vw,56px)', fontWeight: 900, letterSpacing: '-.03em',
            color: '#f8fafc', marginTop: 20, marginBottom: 18 }}>
            Meet customers <span className="g-text">where they are</span>
          </h2>
          <p style={{ fontSize: 17, color: '#475569', maxWidth: 440, margin: '0 auto' }}>
            One AI, three channels. Same context. Same quality. Everywhere.
          </p>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 32 }}>
          <div style={{ display: 'flex', gap: 6, background: 'rgba(255,255,255,.03)',
            border: '1px solid rgba(255,255,255,.06)', borderRadius: 14, padding: 5 }}>
            {channels.map((c, i) => (
              <button key={i} onClick={() => setActive(i)} style={{
                padding: '9px 22px', borderRadius: 10, fontSize: 14, fontWeight: 600,
                cursor: 'pointer', border: 'none', transition: 'all .2s',
                background: active === i ? 'rgba(255,255,255,.08)' : 'transparent',
                color: active === i ? '#f1f5f9' : '#64748b',
                boxShadow: active === i ? '0 2px 16px rgba(0,0,0,.4)' : 'none',
              }}>{c.tab}</button>
            ))}
          </div>
        </div>

        {/* Panel */}
        <div className="card-lift glow-card" style={{ borderRadius: 24, overflow: 'hidden',
          background: 'rgba(255,255,255,.02)', display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
          <div style={{ padding: '48px 44px', borderRight: '1px solid rgba(255,255,255,.05)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
              <div style={{ width: 52, height: 52, borderRadius: 14,
                background: `${ch.color}20`, border: `1px solid ${ch.color}40`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>
                {ch.tab.split(' ')[0]}
              </div>
              <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 99,
                background: `${ch.badge.color}20`, color: ch.badge.color,
                border: `1px solid ${ch.badge.color}40`, textTransform: 'uppercase', letterSpacing: '.06em' }}>
                {ch.badge.label}
              </span>
            </div>
            <h3 style={{ fontSize: 24, fontWeight: 800, color: '#f8fafc', marginBottom: 14, letterSpacing: '-.02em' }}>{ch.title}</h3>
            <p style={{ fontSize: 15, color: '#475569', lineHeight: 1.8, marginBottom: 28 }}>{ch.desc}</p>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 13 }}>
              {ch.points.map(p => (
                <li key={p} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 14, color: '#94a3b8' }}>
                  <div style={{ width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                    background: `${ch.color}20`, border: `1px solid ${ch.color}40`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke={ch.color} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  {p}
                </li>
              ))}
            </ul>
          </div>

          <div style={{ padding: '48px 44px', display: 'flex', flexDirection: 'column', justifyContent: 'center',
            background: `radial-gradient(circle at 70% 30%, ${ch.glow}, transparent 70%)` }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#334155', textTransform: 'uppercase',
              letterSpacing: '.1em', marginBottom: 16 }}>Live Preview</div>
            <div style={{ background: 'rgba(0,0,0,.35)', borderRadius: 16, padding: 20,
              border: `1px solid ${ch.color}25` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12,
                color: '#334155', marginBottom: 12 }}>
                <span>New Ticket · {ch.tab.split(' ')[1] || 'Web'}</span>
                <span>Just now</span>
              </div>
              <div style={{ fontWeight: 700, color: '#f1f5f9', fontSize: 15, marginBottom: 18 }}>
                "My automation workflow isn't triggering"
              </div>
              <div style={{ height: 1, background: 'rgba(255,255,255,.05)', marginBottom: 16 }} />
              <div style={{ padding: '12px 14px', borderRadius: 11,
                background: `${ch.color}12`, border: `1px solid ${ch.color}25`,
                fontSize: 13, color: '#c7d2fe', lineHeight: 1.7 }}>
                <span style={{ color: ch.color, fontWeight: 600 }}>AI Reply: </span>
                "I found the issue! Your webhook trigger needs to be re-authorized. Go to Settings → Integrations → Reconnect. Here's a step-by-step guide..."
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                <span style={{ fontSize: 11, color: '#334155' }}>TKT-A7XP2</span>
                <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 6,
                  background: 'rgba(74,222,128,.1)', color: '#4ade80' }}>✓ Resolved</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── How It Works ────────────────────────────────────────── */
function HowItWorks() {
  const steps = [
    { n: '01', icon: '📨', t: 'Message Received', d: 'Via Email, WhatsApp, or Web Form — instantly normalized into a unified format.' },
    { n: '02', icon: '🔍', t: 'Context Built', d: 'AI fetches ticket history, customer profile, and searches the knowledge base.' },
    { n: '03', icon: '🧠', t: 'AI Responds', d: 'Urooj Waheed generates a personalized reply or escalates with full context.' },
    { n: '04', icon: '✅', t: 'Delivered', d: 'Response sent on the same channel. Ticket updated. Customer delighted.' },
  ];
  return (
    <section id="how-it-works" style={{ padding: '110px 24px', background: '#07070f' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 70 }}>
          <span className="section-label">Process</span>
          <h2 style={{ fontSize: 'clamp(34px,5vw,56px)', fontWeight: 900, letterSpacing: '-.03em',
            color: '#f8fafc', marginTop: 20, marginBottom: 18 }}>
            Resolved in <span className="g-text">under 5 minutes</span>
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, position: 'relative' }}>
          <div style={{ position: 'absolute', top: 36, left: '12.5%', width: '75%', height: 1,
            background: 'linear-gradient(90deg,#4f46e5,#a855f7,#22d3ee)', opacity: .3 }} />
          {steps.map((s, i) => (
            <div key={i} className="card-lift glow-card shimmer" style={{ borderRadius: 20, padding: '30px 22px',
              textAlign: 'center', background: 'rgba(255,255,255,.02)', cursor: 'default' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', margin: '0 auto 20px',
                background: 'linear-gradient(135deg,#4f46e5,#a855f7)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 24, boxShadow: '0 0 30px rgba(79,70,229,.4)', position: 'relative', zIndex: 1 }}>
                {s.icon}
              </div>
              <div style={{ fontSize: 10, fontWeight: 800, color: '#4f46e5', letterSpacing: '.1em',
                textTransform: 'uppercase', marginBottom: 8 }}>{s.n}</div>
              <h4 style={{ fontSize: 16, fontWeight: 700, color: '#f1f5f9', marginBottom: 10 }}>{s.t}</h4>
              <p style={{ fontSize: 13, color: '#475569', lineHeight: 1.7 }}>{s.d}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Tech Stack ──────────────────────────────────────────── */
function TechStack() {
  const stack = [
    ['🧠','Urooj Waheed','AI'],['⚡','FastAPI','Backend'],
    ['🗄️','PostgreSQL+pgvector','Database'],['▲','Next.js 14','Frontend'],
    ['🔴','Redis','Queue'],['📐','OpenAI','Embeddings'],
    ['💬','Meta Cloud API','WhatsApp'],['📧','Gmail OAuth2','Email'],
  ];
  return (
    <section style={{ padding: '80px 24px', borderTop: '1px solid rgba(255,255,255,.05)', background: '#07070f' }}>
      <div style={{ maxWidth: 880, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <h3 style={{ fontSize: 20, fontWeight: 700, color: '#334155' }}>Built on best-in-class infrastructure</h3>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
          {stack.map(([icon, name, cat], i) => (
            <div key={i} className="card-lift shimmer" style={{ borderRadius: 14, padding: '20px 16px',
              textAlign: 'center', background: 'rgba(255,255,255,.02)',
              border: '1px solid rgba(255,255,255,.05)', cursor: 'default' }}>
              <div style={{ fontSize: 26, marginBottom: 8 }}>{icon}</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#cbd5e1', marginBottom: 3 }}>{name}</div>
              <div style={{ fontSize: 11, color: '#334155' }}>{cat}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── CTA ─────────────────────────────────────────────────── */
function CTA() {
  return (
    <section style={{ padding: '110px 24px', background: '#07070f' }}>
      <div style={{ maxWidth: 680, margin: '0 auto', textAlign: 'center',
        borderRadius: 28, padding: '80px 40px',
        background: 'linear-gradient(135deg,rgba(79,70,229,.12),rgba(168,85,247,.08))',
        border: '1px solid rgba(99,102,241,.2)',
        boxShadow: '0 0 100px rgba(79,70,229,.08), inset 0 0 60px rgba(79,70,229,.03)' }}>
        <div style={{ fontSize: 56, marginBottom: 22 }}>🚀</div>
        <h2 style={{ fontSize: 'clamp(30px,5vw,50px)', fontWeight: 900, letterSpacing: '-.03em',
          color: '#f8fafc', marginBottom: 18 }}>Ready to get help?</h2>
        <p style={{ fontSize: 17, color: '#475569', marginBottom: 38, lineHeight: 1.7 }}>
          Submit a ticket and our AI responds in under 5 minutes — no queues, no waiting.
        </p>
        <Link href="/support" className="btn-primary" style={{ fontSize: 17, padding: '16px 38px' }}>
          Open Support Form
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
          </svg>
        </Link>
      </div>
    </section>
  );
}

/* ── Footer ──────────────────────────────────────────────── */
function Footer() {
  const linkStyle = {
    color: '#475569', fontSize: 14, textDecoration: 'none', transition: 'color .2s', display: 'block', marginBottom: 10,
  };
  return (
    <footer style={{ borderTop: '1px solid rgba(255,255,255,.05)', background: '#07070f' }}>

      {/* Main footer body */}
      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '64px 24px 48px',
        display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 40, flexWrap: 'wrap' }}>

        {/* Brand col */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <div style={{ width: 34, height: 34, borderRadius: 10,
              background: 'linear-gradient(135deg,#4f46e5,#a855f7)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px rgba(79,70,229,.4)' }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
            </div>
            <span style={{ color: '#f8fafc', fontWeight: 800, fontSize: 18 }}>FlowForge</span>
          </div>
          <p style={{ color: '#334155', fontSize: 14, lineHeight: 1.8, maxWidth: 260, marginBottom: 24 }}>
            AI-powered customer support across Gmail, WhatsApp, and Web. Tickets resolved in under 5 minutes — 24/7.
          </p>
          {/* Status badge */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '8px 16px', borderRadius: 99,
            background: 'rgba(74,222,128,.06)', border: '1px solid rgba(74,222,128,.2)' }}>
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#4ade80', display: 'inline-block' }} />
            <span style={{ fontSize: 12, color: '#4ade80', fontWeight: 600 }}>All Systems Operational</span>
          </div>
        </div>

        {/* Product links */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#6366f1', letterSpacing: '.1em',
            textTransform: 'uppercase', marginBottom: 18 }}>Product</div>
          {['Features','Channels','How It Works','Tech Stack'].map(l => (
            <a key={l} href={`#${l.toLowerCase().replace(/ /g,'-')}`} style={linkStyle}
              onMouseOver={e=>e.target.style.color='#f1f5f9'}
              onMouseOut={e=>e.target.style.color='#475569'}>{l}</a>
          ))}
        </div>

        {/* Support links */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#a855f7', letterSpacing: '.1em',
            textTransform: 'uppercase', marginBottom: 18 }}>Support</div>
          {[['Get Help','/support'],['Submit Ticket','/support'],['Track Status','/support'],['Documentation','#']].map(([label, href]) => (
            <a key={label} href={href} style={linkStyle}
              onMouseOver={e=>e.target.style.color='#f1f5f9'}
              onMouseOut={e=>e.target.style.color='#475569'}>{label}</a>
          ))}
        </div>

        {/* Built by */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: '#22d3ee', letterSpacing: '.1em',
            textTransform: 'uppercase', marginBottom: 18 }}>Built By</div>
          <div style={{ padding: '16px', borderRadius: 14,
            background: 'rgba(99,102,241,.06)', border: '1px solid rgba(99,102,241,.15)' }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#f1f5f9', marginBottom: 4 }}>Urooj Waheed</div>
            <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.6 }}>
              AI Engineer · FlowForge Customer Success Agent
            </div>
            <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
              {['Gmail','WhatsApp','Web'].map(ch => (
                <span key={ch} style={{ fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
                  background: 'rgba(99,102,241,.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,.2)' }}>{ch}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{ borderTop: '1px solid rgba(255,255,255,.04)', padding: '20px 24px' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <span style={{ color: '#1e293b', fontSize: 12 }}>
            © {new Date().getFullYear()} FlowForge · Built by <span style={{ color: '#6366f1' }}>Urooj Waheed</span>
          </span>
          <span style={{ color: '#1e293b', fontSize: 12 }}>Powered by Urooj Waheed & Three.js</span>
        </div>
      </div>
    </footer>
  );
}

/* ── Page ────────────────────────────────────────────────── */
export default function Home() {
  return (
    <>
      <Nav />
      <Hero />
      <Stats />
      <Features />
      <Channels />
      <HowItWorks />
      <TechStack />
      <CTA />
      <Footer />
    </>
  );
}
