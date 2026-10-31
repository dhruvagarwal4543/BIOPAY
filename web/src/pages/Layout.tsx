import type { ReactNode } from 'react'
import { useAuth } from '../App'
import { api } from '../api'
import { SimBanner } from '../ui'

export default function Layout({ title, children }: { title: string; children: ReactNode }) {
  const { user, setUser } = useAuth()
  const logout = async () => {
    await api('/auth/logout/', { method: 'POST' }).catch(() => {})
    setUser(null)
  }
  return (
    <>
      <SimBanner />
      <header className="border-b border-line bg-ink-900">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-baseline gap-3">
            <span className="text-lg font-semibold tracking-tight">Bio<span className="text-accent">Pay</span></span>
            <span className="hidden text-sm text-muted sm:inline">{title}</span>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="max-w-[10rem] truncate text-muted" title={user?.username}>{user?.name}</span>
            <button onClick={logout} className="rounded border border-line px-3 py-1.5 hover:bg-ink-800">Sign out</button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        <h1 className="text-2xl font-semibold tracking-tight sm:hidden">{title}</h1>
        {children}
      </main>
    </>
  )
}
