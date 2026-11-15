import { createContext, lazy, Suspense, useContext, useEffect, useState, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { api, ApiError, type Role, type User } from './api'
import Admin from './pages/Admin'
import Customer from './pages/Customer'
import Layout from './pages/Layout'
import Login from './pages/Login'
import Merchant from './pages/Merchant'
import { AdminAuditPage, PaymentDetail, Profile, Register, Simulator } from './pages/Extra'
import { ErrorBox, Loading, SimBanner } from './ui'

// gsap + three load only for the public landing, not for the app pages.
const Landing = lazy(() => import('./landing/Landing'))

interface Auth { user: User | null; setUser: (u: User | null) => void }
const AuthCtx = createContext<Auth>({ user: null, setUser: () => {} })
export const useAuth = () => useContext(AuthCtx)

function Protected({ role, children }: { role: Role; children: ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) {
    return (
      <Layout title="Not authorised">
        <div className="slab mx-auto max-w-md bg-ink-900 p-8 text-center">
          <p className="font-serif text-2xl font-bold italic">Wrong desk.</p>
          <p className="mt-2 text-sm text-muted">Your {user.role} account cannot open this page.</p>
          <a href={`/${user.role}`} className="mt-4 inline-block text-accent underline">Go to your dashboard</a>
        </div>
      </Layout>
    )
  }
  return <>{children}</>
}

export default function App() {
  // Public landing must not depend on the API being reachable.
  if (window.location.pathname === '/') return <Suspense fallback={<Loading />}><Landing /></Suspense>
  return <AppShell />
}

function AppShell() {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  useEffect(() => {
    api<{ user: User | null }>('/auth/me/').then(
      (r) => { setUser(r.user); setReady(true) },
      (e) => { setError(e); setReady(true) },
    )
  }, [])
  if (!ready) return <><SimBanner /><Loading /></>
  if (error) return <><SimBanner /><div className="p-6"><ErrorBox error={error} /></div></>
  const home = user ? `/${user.role}` : '/login'
  return (
    <AuthCtx.Provider value={{ user, setUser }}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={user ? <Navigate to={home} replace /> : <Login />} />
          <Route path="/customer" element={<Protected role="customer"><Customer /></Protected>} />
          <Route path="/register" element={user ? <Navigate to={home} replace /> : <Register />} />
          <Route path="/demo" element={<Navigate to={user?.role === 'merchant' ? '/merchant/terminal' : home} replace />} />
          <Route path="/customer/payments/:id" element={<Protected role="customer"><PaymentDetail base="customer" /></Protected>} />
          <Route path="/merchant/payments/:id" element={<Protected role="merchant"><PaymentDetail base="merchant" /></Protected>} />
          <Route path="/merchant/terminal" element={<Protected role="merchant"><Simulator /></Protected>} />
          <Route path="/admin/audit" element={<Protected role="admin"><AdminAuditPage /></Protected>} />
          <Route path="/wallet" element={<Navigate to="/customer" replace />} />
          <Route path="/profile" element={<Protected role="customer"><Profile /></Protected>} />
          <Route path="/merchant" element={<Protected role="merchant"><Merchant /></Protected>} />
          <Route path="/admin" element={<Protected role="admin"><Admin /></Protected>} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </BrowserRouter>
    </AuthCtx.Provider>
  )
}
