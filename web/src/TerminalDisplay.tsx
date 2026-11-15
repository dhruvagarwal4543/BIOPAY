import { useCallback, useEffect, useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import { api } from './api'

interface LiveTerminal {
  id: number; name: string; merchant: string; online: boolean
  screen: string | null; data: { amount?: number; entry?: string; ref?: string; code?: string; mock?: boolean }
}
type Conn = 'connecting' | 'live' | 'offline'

const ERRORS: Record<string, string> = {
  timeout: 'No finger detected', no_match: 'Finger not recognised', no_enrollment: 'Not enrolled here',
  conflict: 'Payment id conflict', server_error: 'Server rejected request', wifi: 'Wi-Fi down', bad_amount: 'Invalid amount',
}

// What the (removed) OLED would have shown, for each screen the device or server reports.
function view(t: LiveTerminal): { title: string; big?: string; sub?: string; tone?: 'ok' | 'bad' | 'warn'; pulse?: boolean } {
  const d = t.data, bc = (n?: number) => `${n ?? 0} BC`
  switch (t.screen) {
    case 'idle': return { title: 'READY', sub: 'Press a key to pay' }
    case 'amount': return { title: 'ENTER AMOUNT', big: d.entry ? `${d.entry}` : '_', sub: '* delete  # confirm' }
    case 'confirm': return { title: 'CONFIRM PAYMENT', big: bc(d.amount), sub: '# pay  * correct' }
    case 'finger': return { title: 'PLACE FINGER', big: bc(d.amount), sub: 'on the sensor', pulse: true }
    case 'matched': return { title: 'FINGER MATCHED', tone: 'ok' }
    case 'no_match': return { title: 'NO MATCH', sub: 'Payment not sent', tone: 'bad' }
    case 'processing': return { title: 'PROCESSING', big: bc(d.amount), pulse: true }
    case 'success': return { title: 'PAID', big: bc(d.amount), sub: `Ref ${d.ref ?? ''}`, tone: 'ok' }
    case 'declined': return { title: 'DECLINED', big: bc(d.amount), sub: `Insufficient BioCoins · Ref ${d.ref ?? ''}`, tone: 'bad' }
    case 'unconfirmed': return { title: 'UNCONFIRMED', sub: 'Retrying the same payment. Do not pay twice.', tone: 'warn', pulse: true }
    case 'error': return { title: 'ERROR', sub: ERRORS[d.code ?? ''] ?? 'Terminal error', tone: 'bad' }
    default: return { title: '—' }
  }
}

const DOT = { live: 'bg-[#3fd14a] shadow-[0_0_6px_#3fd14a]', connecting: 'bg-[#f2b84b]', offline: 'bg-[#8a8170]' }
const LABEL = { live: 'Live', connecting: 'Connecting', offline: 'Offline' }
const TONE = { ok: 'text-lcd-ink', bad: 'text-lcd-ink underline decoration-2', warn: 'text-lcd-ink' }

const saved = () => { try { return localStorage.getItem('biopay.terminal.open') === '1' } catch { return false } }

export default function TerminalDisplay() {
  const [open, setOpen] = useState(saved)
  const [terminals, setTerminals] = useState<LiveTerminal[] | null>(null)
  const [failing, setFailing] = useState(false)
  const [sel, setSel] = useState(0)
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const box = useRef<HTMLDivElement>(null)

  const toggle = () => setOpen((o) => {
    try { localStorage.setItem('biopay.terminal.open', o ? '0' : '1') } catch { /* private mode */ }
    return !o
  })

  // Poll; any failure is "connecting" and the next tick is the reconnect. Slower while collapsed or hidden.
  useEffect(() => {
    let stop = false, timer: number
    const tick = async () => {
      if (!document.hidden) {
        try {
          const r = await api<{ terminals: LiveTerminal[] }>('/merchant/terminals/live/')
          if (!stop) { setTerminals(r.terminals); setFailing(false) }
        } catch { if (!stop) setFailing(true) }
      }
      if (!stop) timer = window.setTimeout(tick, open ? 1000 : 4000)
    }
    tick()
    return () => { stop = true; clearTimeout(timer) }
  }, [open])

  const t = terminals?.[Math.min(sel, (terminals?.length ?? 1) - 1)]
  const conn: Conn = failing || !terminals ? 'connecting' : t?.online ? 'live' : 'offline'

  const drag = useCallback((e: PointerEvent<HTMLElement>) => {
    const el = box.current
    if (!el || (e.target as HTMLElement).closest('button,select')) return
    const r = el.getBoundingClientRect(), x0 = e.clientX, y0 = e.clientY, p0 = pos
    el.setPointerCapture(e.pointerId)
    const move = (m: globalThis.PointerEvent) => setPos({
      x: p0.x + Math.min(Math.max(m.clientX - x0, -r.left), window.innerWidth - r.right),
      y: p0.y + Math.min(Math.max(m.clientY - y0, -r.top), window.innerHeight - r.bottom),
    })
    const up = () => { el.removeEventListener('pointermove', move); el.removeEventListener('pointerup', up) }
    el.addEventListener('pointermove', move); el.addEventListener('pointerup', up)
  }, [pos])

  if (terminals && terminals.length === 0) return null  // no terminal to show: stay out of the way
  const v = conn === 'live' && t ? view(t) : null
  return (
    <div ref={box} style={{ transform: `translate(${pos.x}px, ${pos.y}px)` }}
      className="fixed bottom-4 right-4 z-40 w-[min(18rem,calc(100vw-2rem))] touch-none select-none">
      <div className="slab overflow-hidden rounded-[18px] bg-[#e9e2d2]">
        <div onPointerDown={drag} className="flex cursor-grab items-center gap-2 px-3 py-2 active:cursor-grabbing">
          <span className={`h-2.5 w-2.5 rounded-full ${DOT[conn]} ${conn === 'live' ? 'motion-safe:animate-pulse' : ''}`} />
          <span className="label !text-[10px] font-semibold">Terminal · {LABEL[conn]}</span>
          {terminals && terminals.length > 1 && (
            <select aria-label="Terminal" value={sel} onChange={(e) => setSel(Number(e.target.value))}
              className="ml-1 min-w-0 flex-1 border border-fg bg-ink-900 px-1 text-xs">
              {terminals.map((x, i) => <option key={x.id} value={i}>{x.name}</option>)}
            </select>
          )}
          <button onClick={toggle} aria-expanded={open} aria-label={open ? 'Collapse terminal display' : 'Expand terminal display'}
            className="ml-auto grid h-7 w-7 place-items-center rounded-full border border-fg bg-ink-900 text-fg hover:bg-hi">{open ? '–' : '▢'}</button>
        </div>
        {open && (
          <div className="border-t-[1.5px] border-fg p-3">
            <div role="status" aria-live="polite"
              className="grid h-32 place-content-center gap-1 rounded-md border-[3px] border-[#2b2a25] bg-lcd px-3 text-center font-mono text-lcd-ink shadow-[inset_0_2px_8px_rgba(0,0,0,0.25)]">
              {v ? (
                <div key={t?.screen} className="screen-in">
                  <p className={`text-xs font-semibold tracking-widest ${v.tone ? TONE[v.tone] : 'text-lcd-ink/70'} ${v.pulse ? 'motion-safe:animate-pulse' : ''}`}>{v.title}</p>
                  {v.big && <p className="num my-1 text-3xl font-semibold text-lcd-ink">{v.big}</p>}
                  {v.sub && <p className="text-[11px] text-lcd-ink/75">{v.sub}</p>}
                </div>
              ) : (
                <p className="text-xs text-lcd-ink/70">
                  {conn === 'connecting' ? 'Connecting to server…' : 'Terminal offline. Nothing is shown until the device reports in.'}
                </p>
              )}
            </div>
            <div aria-hidden className="mt-3 grid grid-cols-4 gap-1.5 px-1">
              {'123A456B789C*0#D'.split('').map((k) => (
                <span key={k} className="grid h-5 place-items-center rounded-[4px] border border-fg bg-ink-900 font-mono text-[10px] shadow-[0_2px_0_#16140f]">{k}</span>
              ))}
            </div>
            {v && t?.data.mock && <p className="mt-2 text-[11px] font-semibold text-warn">MOCK terminal · simulated, not a physical fingerprint match</p>}
          </div>
        )}
      </div>
    </div>
  )
}
