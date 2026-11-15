import { useState } from 'react'
import { api, ApiError, money, when, type Enrollment, type Terminal } from '../api'
import { Badge, ErrorBox, Loading, MockNotice, Panel, PaymentsTable, Stat, Table, Td, useApi } from '../ui'
import { AuditPanel } from './Extra'
import Layout from './Layout'

interface Account { id: number; name: string; balance: number }
interface Overview {
  customers: Account[]; merchants: Account[]; terminals: Terminal[]; enrollments: Enrollment[]
  reconciliation: { ok: boolean; problems: string[] }
}

export default function Admin() {
  const { data, error, reload } = useApi<Overview>('/admin/overview/')
  const [actionError, setActionError] = useState<ApiError | null>(null)
  const act = async (path: string, question: string) => {
    if (!confirm(question)) return
    try {
      setActionError(null)
      await api(path, { method: 'POST' })
      reload()
    } catch (e) {
      setActionError(e as ApiError)
    }
  }
  return (
    <Layout title="Administration">
      {error ? <ErrorBox error={error} retry={reload} /> : !data ? <Loading /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Customers" value={data.customers.length} />
            <Stat label="Merchants" value={data.merchants.length} />
            <Stat label="Terminals" value={data.terminals.length} />
            <Stat label="Enrollments" value={data.enrollments.length} />
          </div>
          {actionError && <ErrorBox error={actionError} />}
          <Panel title="Ledger reconciliation">
            {data.reconciliation.ok ? (
              <p className="text-sm"><Badge>SUCCESS</Badge> <span className="ml-2 text-muted">Every wallet equals opening balance + ledger entries; every payment is balanced.</span></p>
            ) : (
              <div role="alert" className="text-sm text-bad">
                <p className="font-semibold">Mismatch detected</p>
                <ul className="mt-2 list-disc pl-5">{data.reconciliation.problems.map((p) => <li key={p}>{p}</li>)}</ul>
              </div>
            )}
          </Panel>
          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Customers">
              <Table head={['Name', 'Balance']}>
                {data.customers.map((c) => <tr key={c.id}><Td>{c.name}</Td><Td num>{money(c.balance)}</Td></tr>)}
              </Table>
            </Panel>
            <Panel title="Merchants">
              <Table head={['Name', 'Balance']}>
                {data.merchants.map((m) => <tr key={m.id}><Td>{m.name}</Td><Td num>{money(m.balance)}</Td></tr>)}
              </Table>
            </Panel>
          </div>
          <Panel title="Terminals">
            <Table head={['Terminal', 'Merchant', 'Status', 'Last seen', '']}>
              {data.terminals.map((t) => (
                <tr key={t.id}>
                  <Td>{t.name}</Td><Td>{t.merchant}</Td><Td><Badge>{t.status}</Badge></Td><Td>{when(t.last_seen)}</Td>
                  <Td>{t.status === 'ACTIVE' && (
                    <button onClick={() => act(`/admin/terminals/${t.id}/revoke/`, `Revoke ${t.name}? Its key stops working immediately.`)} className="border-[1.5px] border-bad px-2 py-1 text-xs font-medium text-bad hover:bg-[#fbe6e1]">Revoke</button>
                  )}</Td>
                </tr>
              ))}
            </Table>
          </Panel>
          <Panel title="Enrollments">
            <div className="space-y-4">
              <MockNotice />
              <Table head={['Customer', 'Terminal', 'Status', 'Source', 'Consent', '']}>
                {data.enrollments.map((e) => (
                  <tr key={e.id}>
                    <Td>{e.customer}</Td><Td>{e.terminal}</Td><Td><Badge>{e.status}</Badge></Td><Td><Badge>{e.source}</Badge></Td><Td>{when(e.consented_at)}</Td>
                    <Td>{e.status !== 'REVOKED' && (
                      <button onClick={() => act(`/admin/enrollments/${e.id}/revoke/`, `Revoke ${e.customer}'s enrollment? Payments with it stop immediately.`)} className="border-[1.5px] border-bad px-2 py-1 text-xs font-medium text-bad hover:bg-[#fbe6e1]">
                        {e.status === 'DELETION_REQUESTED' ? 'Complete deletion' : 'Revoke'}
                      </button>
                    )}</Td>
                  </tr>
                ))}
              </Table>
            </div>
          </Panel>
        </>
      )}
      <AuditPanel />
      <Panel title="Payment records"><PaymentsTable path="/admin/payments/" show={['payer', 'merchant']} /></Panel>
    </Layout>
  )
}
