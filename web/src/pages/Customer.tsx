import { useState } from 'react'
import { api, ApiError, when, type Enrollment } from '../api'
import { Badge, Balance, Empty, ErrorBox, Loading, MockNotice, Panel, PaymentsTable, useApi } from '../ui'
import { EnrollPanel, SimulatorToggle } from './Extra'
import Layout from './Layout'

export default function Customer() {
  const { data, error, reload } = useApi<{ balance: number; simulator_enabled: boolean; enrollments: Enrollment[] }>('/customer/overview/')
  const [actionError, setActionError] = useState<ApiError | null>(null)
  const requestDeletion = async (e: Enrollment) => {
    if (!confirm('Request deletion of this fingerprint enrollment? Payments with it stop immediately.')) return
    try {
      setActionError(null)
      await api(`/customer/enrollments/${e.id}/deletion-request/`, { method: 'POST' })
      reload()
    } catch (err) {
      setActionError(err as ApiError)
    }
  }
  return (
    <Layout title="My wallet">
      {error ? <ErrorBox error={error} retry={reload} /> : !data ? <Loading /> : (
        <>
          <Balance label="Wallet balance" value={data.balance} />
          <Panel title="Biometric enrollment & consent">
            <div className="space-y-4">
              <MockNotice />
              {actionError && <ErrorBox error={actionError} />}
              <EnrollPanel onDone={reload} />
              {data.enrollments.length === 0 ? <Empty>No enrollment yet.</Empty> : (
                <ul className="divide-y divide-line">
                  {data.enrollments.map((e) => (
                    <li key={e.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                      <div className="text-sm">
                        <p className="font-medium">{e.merchant} · {e.terminal} <Badge>{e.status}</Badge> <Badge>{e.source}</Badge> <span className="text-xs text-muted">Mock fingerprint slot {e.sensor_slot}</span></p>
                        <p className="mt-1 text-xs text-muted">
                          Consent given {when(e.consented_at)}
                          {e.deletion_requested_at && ` · Deletion requested ${when(e.deletion_requested_at)}`}
                        </p>
                      </div>
                      {e.status === 'ACTIVE' && (
                        <span className="flex flex-wrap items-center gap-2">
                        {data.simulator_enabled && <SimulatorToggle e={e} onDone={reload} />}
                        <button onClick={() => requestDeletion(e)} className="border-[1.5px] border-bad px-3 py-1.5 text-sm font-medium text-bad hover:bg-[#fbe6e1]">
                          Request deletion
                        </button>
                        </span>
                      )}
                      {e.status === 'DELETION_REQUESTED' && <span className="text-xs text-warn">Awaiting supervisor</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Panel>
        </>
      )}
      <Panel title="Transaction history"><PaymentsTable path="/customer/payments/" detail="/customer/payments" show={['merchant']} /></Panel>
    </Layout>
  )
}
