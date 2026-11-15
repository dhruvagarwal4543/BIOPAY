import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { api, ApiError, money, when, type Page, type Payment } from './api'

export const SIM = 'SIMULATED PAYMENT — NO REAL MONEY'
export const MOCK_FP = 'DEVELOPMENT SIMULATION — NOT A PHYSICAL FINGERPRINT MATCH'

export function SimBanner() {
  return (
    <div role="note" className="overflow-hidden border-b-[1.5px] border-fg bg-fg py-1.5 text-hi">
      <span className="sr-only">{SIM}</span>
      <div aria-hidden className="ticker flex w-max whitespace-nowrap">
        {Array.from({ length: 2 }, (_, k) => (
          <span key={k} className="label flex">
            {Array.from({ length: 6 }, (_, i) => <span key={i} className="px-6">{SIM} ✱</span>)}
          </span>
        ))}
      </div>
    </div>
  )
}

export function MockNotice() {
  return (
    <p role="note" className="label border-[1.5px] border-dashed border-warn bg-[#fff4d6] px-3 py-2 text-warn">
      {MOCK_FP}
    </p>
  )
}

export function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="slab min-w-0 bg-ink-900">
      <header className="flex items-center justify-between gap-3 border-b-[1.5px] border-fg px-4 py-3 sm:px-5">
        <h2 className="text-xl font-semibold italic">{title}</h2>
        {action}
      </header>
      <div className="p-4 sm:p-5">{children}</div>
    </section>
  )
}

export function Balance({ label, value }: { label: string; value: number }) {
  return (
    <div className="slab relative overflow-hidden bg-hi p-5 sm:p-7">
      <p className="label">{label}</p>
      <p className="num mt-3 font-serif text-6xl font-black leading-none tracking-tight sm:text-8xl">
        {money(value)} <span className="font-sans text-lg font-semibold italic text-accent sm:text-2xl">BioCoins</span>
      </p>
      <p className="mt-4 text-xs text-fg/70">{SIM}. BioCoins have no cash value.</p>
      <svg aria-hidden viewBox="0 0 100 100" className="pointer-events-none absolute -right-6 -top-6 h-40 w-40 opacity-25 sm:h-56 sm:w-56">
        {Array.from({ length: 9 }, (_, i) => <ellipse key={i} cx="50" cy="55" rx={6 + i * 5} ry={9 + i * 5.5} fill="none" stroke="currentColor" strokeWidth="1.4" strokeDasharray={i % 3 ? '40 6' : 'none'} />)}
      </svg>
    </div>
  )
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="slab bg-ink-900 px-4 py-3">
      <p className="label text-muted">{label}</p>
      <p className="num mt-1 font-serif text-3xl font-bold">{value}</p>
    </div>
  )
}

const tones: Record<string, string> = {
  SUCCESS: 'border-accent text-accent', ACTIVE: 'border-accent text-accent',
  DECLINED: 'border-bad text-bad', REVOKED: 'border-bad text-bad',
  DELETION_REQUESTED: 'border-warn text-warn', MOCK: 'border-warn text-warn bg-[#fff4d6]',
}
export function Badge({ children }: { children: string }) {
  return (
    <span className={`label inline-block rounded-full border-[1.5px] px-2 py-0.5 !text-[10px] font-semibold ${tones[children] ?? 'border-muted text-muted'}`}>
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
    <div role="alert" className="border-[1.5px] border-bad bg-[#fbe6e1] p-4 text-sm text-bad">
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
          <tr className="label border-b-[1.5px] border-fg text-muted">
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
        <span className="label">{data.count} total</span>
        <span className="flex gap-2">
          <button disabled={!data.previous} onClick={() => setPage(page - 1)} className="border-[1.5px] border-fg px-3 py-1 font-medium text-fg hover:bg-hi disabled:opacity-30">Previous</button>
          <button disabled={!data.next} onClick={() => setPage(page + 1)} className="border-[1.5px] border-fg px-3 py-1 font-medium text-fg hover:bg-hi disabled:opacity-30">Next</button>
        </span>
      </div>
    </div>
  )
}
