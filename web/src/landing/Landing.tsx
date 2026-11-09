import { gsap } from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { Component, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from 'react'

gsap.registerPlugin(ScrollTrigger)
const Scene = lazy(() => import('./Scene'))

// If the 3D scene throws (lost context, shader failure) the page keeps working as plain sections.
class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? null : this.props.children }
}

const hasWebGL = () => {
  try { return !!document.createElement('canvas').getContext('webgl2') } catch { return false }
}

const SCENES = [
  { id: 'identity', h: 'Your Identity. Your Payment.', p: 'Experience a future where your fingerprint is your checkout.' },
  { id: 'scan', h: 'The Scan', p: 'Verification happens on the terminal. Your fingerprint template never reaches the BioPay server.' },
  { id: 'transaction', h: 'The Transaction', p: 'Fingerprint verification → terminal authorization → backend validation → wallet transfer.' },
  { id: 'wallet', h: 'The Digital Wallet', p: 'Debit and credit commit together or not at all. Every payment has one immutable ledger pair.' },
  { id: 'ecosystem', h: 'The Ecosystem', p: 'Customer dashboard, merchant dashboard, admin operations and a physical fingerprint terminal.' },
  { id: 'experience', h: 'Experience BioPay', p: 'Sign in to the live demo, or read how the system works.' },
]

export default function Landing() {
  const progress = useRef(0)
  const root = useRef<HTMLDivElement>(null)
  const [mode] = useState(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    return { gl: hasWebGL(), reduced }
  })

  useEffect(() => {
    if (mode.reduced) return
    const st = ScrollTrigger.create({
      trigger: root.current, start: 'top top', end: 'bottom bottom', scrub: 0.6,
      onUpdate: (s) => { progress.current = s.progress },
    })
    return () => st.kill()
  }, [mode.reduced])

  return (
    <div ref={root} className="relative bg-ink-950 text-fg">
      <div className="fixed inset-x-0 top-0 z-50 bg-accent-dim px-4 py-1 text-center text-xs font-medium tracking-wide">
        SIMULATED PAYMENT — NO REAL MONEY
      </div>
      {mode.gl && (
        <div className="fixed inset-0 z-0">
          <SceneBoundary><Suspense fallback={<p role="status" className="pt-24 text-center text-sm text-muted">Loading 3D scene…</p>}><Scene progress={progress} still={mode.reduced} /></Suspense></SceneBoundary>
        </div>
      )}
      <nav className="fixed inset-x-0 top-8 z-40 flex items-center justify-between px-6">
        <span className="text-lg font-semibold tracking-tight">Bio<span className="text-accent">Pay</span></span>
        <a href="/login" className="rounded-full border border-line px-4 py-1.5 text-sm hover:border-accent">Sign in</a>
      </nav>
      <main className="relative z-10">
        {SCENES.map((s, i) => (
          <section key={s.id} id={s.id} className="flex min-h-screen items-center px-6 md:px-16">
            <div className="max-w-xl rounded-2xl bg-ink-950/60 p-6 backdrop-blur-sm">
              {i === 0 ? <h1 className="text-4xl font-semibold tracking-tight md:text-6xl">{s.h}</h1>
                : <h2 className="text-3xl font-semibold tracking-tight md:text-5xl">{s.h}</h2>}
              <p className="mt-4 text-lg text-muted">{s.p}</p>
              {i === 0 && (
                <div className="mt-8 flex gap-3">
                  <a href="#scan" className="rounded-full bg-accent px-5 py-2.5 font-medium text-ink-950">Explore BioPay</a>
                  <a href="/login" className="rounded-full border border-line px-5 py-2.5">Launch Demo</a>
                </div>
              )}
              {i === 1 && <p className="num mt-4 text-sm text-accent" role="status">Authentication progress follows your scroll</p>}
              {i === 5 && (
                <div className="mt-8 flex gap-3">
                  <a href="/login" className="rounded-full bg-accent px-5 py-2.5 font-medium text-ink-950">Launch Demo</a>
                  <a href="/login" className="rounded-full border border-line px-5 py-2.5">Sign in</a>
                </div>
              )}
            </div>
          </section>
        ))}
      </main>
    </div>
  )
}
