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

const SIM = 'SIMULATED PAYMENT — NO REAL MONEY'

type Spec = [string, string]
const CHAPTERS: { id: string; no: string; kicker: string; h: ReactNode; p: string; specs: Spec[] }[] = [
  {
    id: 'sensor', no: '01', kicker: 'The sensor keeps the secret',
    h: <>Your print never <span className="marker">leaves the glass</span>.</>,
    p: 'The R307S module stores each template in its own memory and searches it one-to-many on the module. The terminal only learns a slot number, and the server only ever sees that number.',
    specs: [['Module', 'R307S optical'], ['Link', 'UART2 · 57600 baud'], ['Leaves the sensor', 'slot number only']],
  },
  {
    id: 'terminal', no: '02', kicker: 'An exploded terminal',
    h: <>Sixteen keys, one LED, <span className="marker">no screen</span>.</>,
    p: 'An ESP32 NodeMCU-32S reads the amount from a 4×4 keypad, asks for a finger, and posts the slot and amount to the server with its own revocable key. One LED tells the whole story in blink patterns.',
    specs: [['Controller', 'ESP32 NodeMCU-32S'], ['Keypad', 'GPIO 32 33 25 26 / 27 14 18 19'], ['Status LED', 'GPIO 4']],
  },
  {
    id: 'ledger', no: '03', kicker: 'Money moves exactly once',
    h: <>A lost reply <span className="marker">never charges twice</span>.</>,
    p: 'Each payment gets a UUID that is written to flash before it is sent. Retries reuse it, so the server either returns the stored result or commits one debit and one credit together, in a single locked transaction.',
    specs: [['Ledger', 'double entry, sums to zero'], ['Retry', 'same UUID after reboot'], ['Check', 'manage.py reconcile']],
  },
  {
    id: 'screens', no: '04', kicker: 'A screen that lives on the web',
    h: <>The display moved <span className="marker">to your browser</span>.</>,
    p: 'The terminal reports what it is showing, and the website mirrors it live for the merchant. The PAID or DECLINED line is written by the server, never by the device. Customers, merchants and admins each get their own desk.',
    specs: [['Heartbeat', 'every 5 s'], ['Offline after', '15 s silence'], ['Roles', 'customer · merchant · admin']],
  },
]

function Ticker({ text, invert }: { text: string; invert?: boolean }) {
  return (
    <div className={`overflow-hidden border-y-[1.5px] border-fg py-2 ${invert ? 'bg-fg text-hi' : 'bg-hi text-fg'}`} aria-hidden>
      <div className="ticker flex w-max whitespace-nowrap">
        {Array.from({ length: 12 }, (_, i) => <span key={i} className="label px-6">{text} ✱</span>)}
      </div>
    </div>
  )
}

function Seal() {
  // rotating rubber-stamp seal next to the headline
  const t = 'NO PHONE · NO CARD · NO PIN · JUST A FINGER · '
  return (
    <svg viewBox="0 0 200 200" className="h-28 w-28 motion-safe:animate-[spin_22s_linear_infinite] sm:h-36 sm:w-36" aria-hidden>
      <defs><path id="seal" d="M100,100 m-78,0 a78,78 0 1,1 156,0 a78,78 0 1,1 -156,0" /></defs>
      <circle cx="100" cy="100" r="96" fill="#e6ff3a" stroke="#16140f" strokeWidth="3" />
      <circle cx="100" cy="100" r="58" fill="none" stroke="#16140f" strokeWidth="1.5" strokeDasharray="4 4" />
      <text fontFamily="JetBrains Mono, monospace" fontSize="13" fontWeight="600" letterSpacing="2" fill="#16140f">
        <textPath href="#seal">{t}</textPath>
      </text>
      <text x="100" y="112" textAnchor="middle" fontFamily="Fraunces, serif" fontStyle="italic" fontWeight="900" fontSize="34" fill="#16140f">✱</text>
    </svg>
  )
}

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
    <div ref={root} className="relative text-fg">
      <div role="note" className="fixed inset-x-0 top-0 z-50 border-b-[1.5px] border-fg bg-fg py-1 text-center">
        <span className="label text-hi">{SIM}</span>
      </div>
      {mode.gl && (
        <div className="pointer-events-none fixed inset-0 z-0">
          <SceneBoundary>
            <Suspense fallback={<p role="status" className="label pt-28 text-center text-muted">Drawing the terminal…</p>}>
              <Scene progress={progress} still={mode.reduced} />
            </Suspense>
          </SceneBoundary>
        </div>
      )}
      <nav className="fixed inset-x-0 top-7 z-40 flex items-center justify-between px-4 py-3 sm:px-8">
        <a href="/" className="font-serif text-2xl font-black italic tracking-tight">Bio<span className="text-accent">Pay</span></a>
        <div className="flex items-center gap-2 sm:gap-4">
          <a href="#ledger" className="label hidden hover:underline sm:inline">How it works</a>
          <a href="/register" className="label hidden hover:underline sm:inline">Register</a>
          <a href="/login" className="slab press bg-ink-900 px-4 py-1.5 text-sm font-semibold">Sign in</a>
        </div>
      </nav>

      <main className="relative z-10">
        {/* masthead */}
        <section id="ridge" className="flex min-h-screen flex-col justify-end px-4 pb-10 pt-28 sm:px-8 md:justify-center md:pb-0">
          <div className="max-w-3xl">
            <p className="label inline-flex flex-wrap gap-x-4 bg-ink-950 py-1 pr-2 text-muted"><span>Vol. 01</span><span>The fingerprint issue</span><span>IoT · ESP32 · R307S</span></p>
            <div className="mt-4 flex items-start gap-4">
              <h1 className="font-serif text-[clamp(3rem,9vw,7.5rem)] font-black leading-[0.86] tracking-tight">
                Pay with the <em className="text-accent">ridges</em> of your <span className="marker">finger</span>.
              </h1>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-6">
              <p className="max-w-md bg-ink-950/80 text-lg leading-snug">
                BioPay is a checkout terminal that needs no phone, card or PIN. Type an amount, touch the sensor, done. A college IoT build, paid in simulated BioCoins.
              </p>
              <Seal />
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#sensor" className="slab press bg-accent px-5 py-3 font-semibold text-ink-900">Explore BioPay ↓</a>
              <a href="/login" className="slab press bg-ink-900 px-5 py-3 font-semibold">Launch Demo</a>
            </div>
          </div>
        </section>

        <Ticker text="Template stays on the sensor · Slot + amount over HTTPS · One UUID per payment · Debit and credit commit together" />

        {CHAPTERS.map((c) => (
          <section key={c.id} id={c.id} className="flex min-h-screen items-end px-4 pb-12 pt-24 sm:px-8 md:items-center md:pb-0">
            <article className="slab w-full max-w-xl bg-ink-900/95 p-6 sm:p-8">
              <header className="flex items-baseline justify-between gap-4 border-b-[1.5px] border-fg pb-3">
                <span className="label">{c.kicker}</span>
                <span aria-hidden className="font-serif text-5xl font-black italic leading-none text-transparent [-webkit-text-stroke:1.5px_#16140f]">{c.no}</span>
              </header>
              <h2 className="mt-5 text-4xl font-black leading-[0.95] sm:text-5xl">{c.h}</h2>
              <p className="mt-4 text-[17px] leading-relaxed">{c.p}</p>
              <dl className="mt-6 grid gap-px border-[1.5px] border-fg bg-fg sm:grid-cols-3">
                {c.specs.map(([k, val]) => (
                  <div key={k} className="bg-ink-950 p-3">
                    <dt className="label !text-[10px] text-muted">{k}</dt>
                    <dd className="mt-1 font-mono text-[13px] font-semibold">{val}</dd>
                  </div>
                ))}
              </dl>
            </article>
          </section>
        ))}

        <section id="join" className="flex min-h-screen flex-col justify-end pt-24">
          <div className="px-4 pb-16 sm:px-8 md:pb-24">
            <div className="slab max-w-2xl bg-hi p-6 sm:p-10">
              <p className="label">Try it · local demo</p>
              <h2 className="mt-3 text-5xl font-black leading-[0.9] sm:text-7xl">Experience BioPay.</h2>
              <p className="mt-4 max-w-md text-lg">Register as a customer, enrol a finger, then charge it from the merchant desk and watch the terminal screen change.</p>
              <div className="mt-7 flex flex-wrap gap-3">
                <a href="/login" className="slab press bg-fg px-5 py-3 font-semibold text-hi">Launch Demo</a>
                <a href="/register" className="slab press bg-ink-900 px-5 py-3 font-semibold">Create an account</a>
              </div>
            </div>
          </div>
          <Ticker text={SIM} invert />
          <footer className="flex flex-wrap items-center justify-between gap-3 bg-ink-950 px-4 py-5 sm:px-8">
            <span className="font-serif text-xl font-black italic">Bio<span className="text-accent">Pay</span></span>
            <span className="label text-muted">Django · PostgreSQL · React · Three.js · ESP32 · R307S</span>
          </footer>
        </section>
      </main>
    </div>
  )
}
