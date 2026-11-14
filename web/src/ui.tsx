import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, money, when, type Page, type Payment } from './api'

export const SIM = 'SIMULATED PAYMENT — NO REAL MONEY'
export const MOCK_FP = 'DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH'

export function SimBanner() {
  return (
    <div role="note" className="border-b border-line bg-ink-900 px-4 py-2 text-center text-xs font-semibold tracking-widest text-warn">
      {SIM}
    </div>
  )
}

export function MockNotice() {
  return (
    <p role="note" className="rounded-md border border-warn/40 bg-warn/10 px-3 py-2 text-xs font-semibold tracking-wide text-warn">
      {MOCK_FP}
    </p>
  )
}

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-lg border border-line bg-ink-900">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">{title}</h2>
        {action}
      </header>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  )
}

export function Balance({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-ink-900 p-5 sm:p-6">
      <p className="text-sm text-muted">{label}</p>
      <p className="num mt-2 text-5xl font-semibold tracking-tight">
        {money(value)} <span className="text-lg font-medium text-accent">BioCoins</span>
      </p>
      <p className="mt-2 text-xs text-muted">{SIM}. BioCoins have no cash value.</p>
    </div>
  )
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-ink-900 px-4 py-3">
      <p className="text-xs text-muted">{label}</p>
      <p className="num mt-1 text-2xl font-semibold">{value}</p>
    </div>
  )
}

const tones: Record<string, string> = {
  SUCCESS: 'bg-accent/15 text-accent', ACTIVE: 'bg-accent/15 text-accent',
  DECLINED: 'bg-bad/15 text-bad', REVOKED: 'bg-bad/15 text-bad',
  DELETION_REQUESTED: 'bg-warn/15 text-warn', MOCK: 'bg-warn/15 text-warn',
}
export function Badge({ children }: { children: string }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${tones[children] ?? 'bg-ink-800 text-muted'}`}>
      {children.replace('_', ' ')}
    </span>
  )
}

export function Loading({ what = 'Loading' }: { what?: string }) {
  return <p role="status" className="py-6 text-center text-sm text-muted">{what}…</p>
}
export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>
}
export function ErrorBox({ error, retry }: { error: ApiError; retry?: () => void }) {
  return (
    <div role="alert" className="rounded-md border border-bad/40 bg-bad/10 p-4 text-sm text-bad">
      {error.message}
      {retry && (
        <button onClick={retry} className="ml-3 underline">Retry</button>
      )}
    </div>
  )
}

export function useApi<T>(path: string) {
  const [tick, setTick] = useState(0)
  // The result is tagged with the request it answers, so "loading" is derived (no setState in the effect).
  const key = `${path}#${tick}`
  const [result, setResult] = useState<{ key: string; data?: T; error?: ApiError }>({ key: '' })
  useEffect(() => {
    let live = true
    api<T>(path).then(
      (data) => live && setResult({ key, data }),
      (error) => live && setResult({ key, error }),
    )
    return () => { live = false }
  }, [path, key])
  const loading = result.key !== key
  // Keep the last data while refreshing; drop an old error as soon as a new request starts.
  return { data: result.data, error: loading ? undefined : result.error, loading, reload: useCallback(() => setTick((t) => t + 1), []) }
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[32rem] text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs uppercase tracking-wider text-muted">
            {head.map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium sm:px-3">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  )
}
export const Td = ({ children, num }: { children: ReactNode; num?: boolean }) => (
  <td className={`px-4 py-3 sm:px-3 ${num ? 'num text-right' : ''}`}>{children}</td>
)

export function PaymentsTable({ path, show, detail }: { path: string; show: ('payer' | 'merchant')[]; detail?: string }) {
  const [page, setPage] = useState(1)
  const { data, error, loading, reload } = useApi<Page<Payment>>(`${path}?page=${page}`)
  if (error) return <ErrorBox error={error} retry={reload} />
  if (!data) return <Loading what="Loading transactions" />
  if (data.count === 0) return <Empty>No transactions yet.</Empty>
  return (
    <div className={loading ? 'opacity-60' : ''}>
      <Table head={['Time', ...show.map((s) => (s === 'payer' ? 'Customer' : 'Merchant')), 'Amount', 'Status', 'Verification']}>
        {data.results.map((p) => (
          <tr key={p.payment_id}>
            <Td>{detail ? <a className="text-accent underline" href={`${detail}/${p.payment_id}`}>{when(p.created_at)}</a> : when(p.created_at)}</Td>
            {show.map((s) => <Td key={s}>{p[s]}</Td>)}
            <Td num>{money(p.amount)}</Td>
            <Td><Badge>{p.status}</Badge></Td>
            <Td><Badge>{p.auth_method}</Badge></Td>
          </tr>
        ))}
      </Table>
      <div className="mt-3 flex items-center justify-between text-xs text-muted">
        <span>{data.count} total</span>
        <span className="flex gap-2">
          <button disabled={!data.previous} onClick={() => setPage(page - 1)} className="rounded border border-line px-3 py-1 disabled:opacity-40">Previous</button>
          <button disabled={!data.next} onClick={() => setPage(page + 1)} className="rounded border border-line px-3 py-1 disabled:opacity-40">Next</button>
        </span>
      </div>
    </div>
  )
}
