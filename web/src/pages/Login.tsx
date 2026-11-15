import { useState, type FormEvent } from 'react'
import { useAuth } from '../App'
import { api, ApiError, type User } from '../api'
import { SimBanner } from '../ui'

export default function Login() {
  const { setUser } = useAuth()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const f = new FormData(e.currentTarget)
    setBusy(true)
    setError('')
    try {
      await fetch('/api/auth/csrf/', { credentials: 'same-origin' })
      const r = await api<{ user: User }>('/auth/login/', {
        method: 'POST', body: { username: f.get('username'), password: f.get('password') },
      })
      setUser(r.user)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Sign-in failed.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <SimBanner />
      <main className="mx-auto grid w-full max-w-5xl items-center gap-10 px-4 py-12 md:grid-cols-[1.1fr_1fr] md:py-20">
        <div>
          <p className="label text-muted">Checkout without a phone · Vol. 01</p>
          <h1 className="mt-3 font-serif text-6xl font-black italic leading-[0.9] tracking-tight sm:text-8xl">Bio<span className="text-accent">Pay</span></h1>
          <p className="mt-5 max-w-sm text-lg leading-snug">Phone-free biometric checkout — <span className="marker">university demonstration</span>.</p>
          <svg aria-hidden viewBox="0 0 120 120" className="mt-8 hidden h-40 w-40 text-fg md:block">
            {Array.from({ length: 11 }, (_, i) => (
              <path key={i} fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"
                strokeDasharray={i % 4 === 2 ? '22 5' : undefined}
                d={`M ${60 - 6 - i * 4.6} 112 C ${60 - 6 - i * 4.6} ${48 - i * 3}, ${60 + 6 + i * 4.6} ${48 - i * 3}, ${60 + 6 + i * 4.6} ${100 - i}`} />
            ))}
          </svg>
        </div>
        <form onSubmit={submit} className="slab space-y-4 bg-ink-900 p-6">
          <p className="label border-b-[1.5px] border-fg pb-3">Sign in · Form B-1</p>
          <label className="block text-sm">
            <span className="label text-muted">Username</span>
            <input name="username" autoComplete="username" required className="mt-1 w-full border-[1.5px] border-fg px-3 py-2" />
          </label>
          <label className="block text-sm">
            <span className="label text-muted">Password</span>
            <input name="password" type="password" autoComplete="current-password" required className="mt-1 w-full border-[1.5px] border-fg px-3 py-2" />
          </label>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button disabled={busy} className="slab press w-full bg-accent px-4 py-2.5 font-semibold text-ink-900 disabled:opacity-60">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
          <p className="text-center text-sm text-muted">New here? <a className="font-semibold text-accent underline decoration-2 underline-offset-2" href="/register">Create an account</a></p>
        </form>
      </main>
    </>
  )
}
