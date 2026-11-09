import { when, type Terminal } from '../api'
import { Badge, Balance, Empty, ErrorBox, Loading, MockNotice, Panel, PaymentsTable, Table, Td, useApi } from '../ui'
import { Link } from 'react-router-dom'
import Layout from './Layout'

export default function Merchant() {
  const { data, error, reload } = useApi<{ balance: number; terminals: Terminal[] }>('/merchant/overview/')
  return (
    <Layout title="Merchant">
      {error ? <ErrorBox error={error} retry={reload} /> : !data ? <Loading /> : (
        <>
          <Balance label="Merchant balance" value={data.balance} />
          <Panel title="Terminals" action={<Link to="/merchant/terminal" className="text-sm text-accent underline">Open simulator</Link>}>
            <div className="space-y-4">
              <MockNotice />
              {data.terminals.length === 0 ? <Empty>No terminal assigned.</Empty> : (
                <Table head={['Terminal', 'Status', 'Last seen']}>
                  {data.terminals.map((t) => (
                    <tr key={t.id}><Td>{t.name}</Td><Td><Badge>{t.status}</Badge></Td><Td>{when(t.last_seen)}</Td></tr>
                  ))}
                </Table>
              )}
            </div>
          </Panel>
        </>
      )}
      <Panel title="Payment records"><PaymentsTable path="/merchant/payments/" detail="/merchant/payments" show={['payer']} /></Panel>
    </Layout>
  )
}
