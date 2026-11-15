import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../App'
import { api } from '../api'
import { SimBanner } from '../ui'
import TerminalDisplay from '../TerminalDisplay'

const NAV: Record<string, [string, string][]> = {
  customer: [['/customer', 'Wallet'], ['/profile', 'Profile']],
  merchant: [['/merchant', 'Dashboard'], ['/merchant/terminal', 'Simulator']],
  admin: [['/admin', 'Overview'], ['/admin/audit', 'Audit log']],
}

export default function Layout({ title, children }: { title: string; children: ReactNode }) {
  const { user, setUser } = useAuth()
  const logout = async () => {
    await api('/auth/logout/', { method: 'POST' }).catch(() => {})
    setUser(null)
  }
  return (
    <>
      <SimBanner />
      <header className="border-b-[1.5px] border-fg bg-ink-950/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-end justify-between gap-3 px-4 pb-3 pt-4">
          <div className="flex min-w-0 items-end gap-4">
            <a href="/" className="font-serif text-3xl font-black italic leading-none tracking-tight">Bio<span className="text-accent">Pay</span></a>
            <span className="label hidden truncate pb-0.5 text-muted sm:inline">No. {String(new Date().getDate()).padStart(2, '0')} · {title}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden max-w-[10rem] truncate italic text-muted sm:inline" title={user?.username}>{user?.name}</span>
            <button onClick={logout} className="slab press bg-ink-900 px-3 py-1.5 text-sm font-semibold">Sign out</button>
          </div>
        </div>
        <nav aria-label="Main" className="mx-auto max-w-6xl px-4">
          <ul className="flex gap-1 text-sm">
            {(NAV[user?.role ?? ''] ?? []).map(([to, label], i) => (
              <li key={to}><NavLink to={to} end className={({ isActive }) => `label inline-block border-x-[1.5px] border-t-[1.5px] px-3 py-2 ${isActive ? 'border-fg bg-hi text-fg' : 'border-transparent text-muted hover:text-fg'}`}><span className="mr-1 text-muted">0{i + 1}</span>{label}</NavLink></li>
            ))}
          </ul>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl space-y-7 px-4 py-8">
        <h1 className="text-4xl font-black italic tracking-tight sm:text-5xl">{title}</h1>
        {children}
      </main>
      {(user?.role === 'merchant' || user?.role === 'admin') && <TerminalDisplay />}
    </>
  )
}
