import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../App'
import { api, ApiError, money, when, type Page, type Payment, type User } from '../api'
import { Badge, Empty, ErrorBox, Loading, MockNotice, Panel, SimBanner, Table, Td, useApi } from '../ui'
import Layout from './Layout'

const input = 'mt-1 w-full rounded border border-line bg-ink-950 px-3 py-2'

export function Register() {
  const { setUser } = useAuth()
  const [error, setError] = useState('')
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setError('')
    try {
      await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
      const r = await api<{ user: User }>('/auth/register/', {
        method: 'POST',
        body: { username: f.get('username'), name: f.get('name'), password: f.get('password'), consent: f.get('consent') === 'on' },
      })
      setUser(r.user)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Registration failed.')
    }
  }
  return (
    <>
      <SimBanner />
      <main className="mx-auto mt-12 w-full max-w-sm px-4">
        <h1 className="text-3xl font-semibold tracking-tight">Create your account</h1>
        <form onSubmit={submit} className="mt-6 space-y-4 rounded-lg border border-line bg-ink-900 p-5">
          <label className="block text-sm"><span className="text-muted">Full name</span><input name="name" required maxLength={100} className={input} /></label>
          <label className="block text-sm"><span className="text-muted">Username (lowercase, digits, hyphen)</span><input name="username" autoComplete="username" required pattern="[a-z0-9][a-z0-9\-]{2,29}" className={input} /></label>
          <label className="block text-sm"><span className="text-muted">Password (12+ characters)</span><input name="password" type="password" autoComplete="new-password" minLength={12} required className={input} /></label>
          <label className="flex gap-2 text-sm"><input name="consent" type="checkbox" required className="mt-1" />
            <span>I consent to the simulated fingerprint demo. BioCoins have no monetary value and no real biometric data is collected.</span></label>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button className="w-full rounded bg-accent px-4 py-2 font-semibold text-ink-950">Register</button>
          <p className="text-center text-sm text-muted">Have an account? <a className="text-accent underline" href="/login">Sign in</a></p>
        </form>
      </main>
    </>
  )
}

export function EnrollPanel({ onDone }: { onDone: () => void }) {
  const { data } = useApi<{ mock_enrollment: boolean; terminals: { id: number; name: string; merchant: string }[] }>('/customer/terminals/')
  const [error, setError] = useState<ApiError | null>(null)
  if (!data?.mock_enrollment) return null
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    try {
      setError(null)
      await api('/customer/enroll/', { method: 'POST', body: { terminal_id: Number(f.get('terminal')), consent: f.get('consent') === 'on' } })
      onDone()
    } catch (err) { setError(err as ApiError) }
  }
  return (
    <form onSubmit={submit} className="space-y-3 rounded border border-line p-3">
      <p className="text-sm font-medium">Add a simulated enrollment</p>
      {error && <ErrorBox error={error} />}
      <select name="terminal" required aria-label="Terminal" className={input}>
        {data.terminals.map((t) => <option key={t.id} value={t.id}>{t.merchant} · {t.name}</option>)}
      </select>
      <label className="flex gap-2 text-sm"><input name="consent" type="checkbox" required className="mt-1" /><span>I consent to enrolling a simulated fingerprint on this terminal. I can withdraw at any time.</span></label>
      <button className="rounded bg-accent px-3 py-1.5 text-sm font-semibold text-ink-950">Enroll (MOCK)</button>
    </form>
  )
}

export function PaymentDetail({ base }: { base: 'customer' | 'merchant' }) {
  const { id } = useParams()
  const { data, error, reload } = useApi<{ payment: Payment }>(`/${base}/payments/${id}/`)
  const back = `/${base}`
  return (
    <Layout title="Transaction">
      <Link to={back} className="text-sm text-accent underline">← Back</Link>
      {error ? <ErrorBox error={error} retry={reload} /> : !data ? <Loading /> : (
        <Panel title="Transaction details">
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            {([['Payment ID', data.payment.payment_id], ['Time', when(data.payment.created_at)], ['Customer', data.payment.payer],
              ['Merchant', data.payment.merchant], ['Amount', `${money(data.payment.amount)} BioCoins`],
              ['Verification', data.payment.auth_method], ['Reason', data.payment.decline_reason || '—']] as const).map(([k, v]) => (
              <div key={k}><dt className="text-muted">{k}</dt><dd className="num break-all">{v}</dd></div>
            ))}
            <div><dt className="text-muted">Status</dt><dd><Badge>{data.payment.status}</Badge></dd></div>
          </dl>
        </Panel>
      )}
    </Layout>
  )
}

type Outcome = { kind: 'idle' | 'pending' | 'success' | 'declined' | 'unauthorized' | 'revoked' | 'network' | 'error'; msg?: string }

export function Simulator() {
  const { data, error } = useApi<{ terminals: { id: number; name: string; status: string }[] }>('/merchant/overview/')
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })
  // One UUID per payment attempt; a retry after a network error reuses it, a new payment makes a new one.
  const [attempt, setAttempt] = useState<{ id: string; sig: string } | null>(null)
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    const body = { terminal_id: Number(f.get('terminal')), sensor_slot: Number(f.get('slot')), amount: Number(f.get('amount')) }
    const sig = JSON.stringify(body)
    const id = attempt?.sig === sig && outcome.kind === 'network' ? attempt.id : crypto.randomUUID()
    setAttempt({ id, sig })
    setOutcome({ kind: 'pending' })
    try {
      const r = await api<{ replayed: boolean }>('/merchant/simulate/', { method: 'POST', body: { ...body, payment_id: id } })
      setOutcome({ kind: 'success', msg: r.replayed ? 'Confirmed (replayed, charged once).' : 'Payment confirmed by the server.' })
    } catch (err) {
      const a = err as ApiError
      if (a.status === 0) setOutcome({ kind: 'network', msg: a.message + ' Press Pay again to retry the same payment.' })
      else if (a.status === 422) setOutcome({ kind: 'declined', msg: 'Insufficient BioCoins.' })
      else if (a.code === 'terminal_revoked') setOutcome({ kind: 'revoked', msg: a.message })
      else if (a.status === 403) setOutcome({ kind: 'unauthorized', msg: 'No active enrollment for that fingerprint slot.' })
      else setOutcome({ kind: 'error', msg: a.message })
    }
  }
  const tone = outcome.kind === 'success' ? 'text-accent' : outcome.kind === 'pending' || outcome.kind === 'idle' ? 'text-muted' : 'text-bad'
  return (
    <Layout title="Terminal simulator">
      <MockNotice />
      {error ? <ErrorBox error={error} /> : !data ? <Loading /> : data.terminals.filter((t) => t.status === 'ACTIVE').length === 0 ? <Empty>No active terminal. Ask an admin to issue one.</Empty> : (
        <Panel title="Simulated checkout">
          <form onSubmit={submit} className="grid gap-4 sm:max-w-md">
            <label className="text-sm"><span className="text-muted">Terminal</span>
              <select name="terminal" className={input}>{data.terminals.filter((t) => t.status === 'ACTIVE').map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
            <label className="text-sm"><span className="text-muted">Mock fingerprint slot</span><input name="slot" type="number" min={0} step={1} required defaultValue={1} className={input} /></label>
            <label className="text-sm"><span className="text-muted">Amount (BioCoins)</span><input name="amount" type="number" min={1} step={1} required defaultValue={10} className={input} /></label>
            <button disabled={outcome.kind === 'pending'} className="rounded bg-accent px-4 py-2 font-semibold text-ink-950 disabled:opacity-60">
              {outcome.kind === 'network' ? 'Retry payment' : 'Pay'}
            </button>
          </form>
          <p role="status" className={`mt-4 text-sm ${tone}`}>
            {outcome.kind === 'idle' ? 'Waiting.' : outcome.kind === 'pending' ? 'Waiting for server confirmation…' : `${outcome.kind.toUpperCase()}: ${outcome.msg}`}
          </p>
        </Panel>
      )}
    </Layout>
  )
}

interface Audit { id: number; actor: string; action: string; detail: string; created_at: string }
export function AuditPanel() {
  const [page, setPage] = useState(1)
  const { data, error, reload } = useApi<Page<Audit>>(`/admin/audit/?page=${page}`)
  return (
    <Panel title="Audit log">
      {error ? <ErrorBox error={error} retry={reload} /> : !data ? <Loading /> : data.count === 0 ? <Empty>No events yet.</Empty> : (
        <>
          <Table head={['Time', 'Actor', 'Action', 'Detail']}>
            {data.results.map((a) => <tr key={a.id}><Td>{when(a.created_at)}</Td><Td>{a.actor}</Td><Td>{a.action}</Td><Td>{a.detail}</Td></tr>)}
          </Table>
          <div className="mt-3 flex items-center justify-between text-xs text-muted">
            <span>{data.count} events</span>
            <span className="flex gap-2">
              <button disabled={!data.previous} onClick={() => setPage(page - 1)} className="rounded border border-line px-3 py-1 disabled:opacity-40">Previous</button>
              <button disabled={!data.next} onClick={() => setPage(page + 1)} className="rounded border border-line px-3 py-1 disabled:opacity-40">Next</button>
            </span>
          </div>
        </>
      )}
    </Panel>
  )
}

export function AdminAuditPage() {
  return <Layout title="Audit log"><Link to="/admin" className="text-sm text-accent underline">← Admin</Link><AuditPanel /></Layout>
}
