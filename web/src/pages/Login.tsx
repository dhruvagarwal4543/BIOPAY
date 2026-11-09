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
      <main className="mx-auto mt-16 w-full max-w-sm px-4">
        <h1 className="text-3xl font-semibold tracking-tight">Bio<span className="text-accent">Pay</span></h1>
        <p className="mt-1 text-sm text-muted">Phone-free biometric checkout — university demonstration.</p>
        <form onSubmit={submit} className="mt-8 space-y-4 rounded-lg border border-line bg-ink-900 p-5">
          <label className="block text-sm">
            <span className="text-muted">Username</span>
            <input name="username" autoComplete="username" required className="mt-1 w-full rounded border border-line bg-ink-950 px-3 py-2" />
          </label>
          <label className="block text-sm">
            <span className="text-muted">Password</span>
            <input name="password" type="password" autoComplete="current-password" required className="mt-1 w-full rounded border border-line bg-ink-950 px-3 py-2" />
          </label>
          {error && <p role="alert" className="text-sm text-bad">{error}</p>}
          <button disabled={busy} className="w-full rounded bg-accent px-4 py-2 font-semibold text-ink-950 disabled:opacity-60">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted">New here? <a className="text-accent underline" href="/register">Create an account</a></p>
      </main>
    </>
  )
}
