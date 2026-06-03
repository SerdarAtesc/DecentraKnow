import { useState, useEffect, useCallback } from 'react'
import { Wallet, ArrowDownToLine, ArrowUpFromLine, Coins, Loader2, RefreshCw } from 'lucide-react'
import { useWallet } from '../hooks/useWallet'
import { api } from '../services/api'
import { soroban } from '../services/soroban'
import { toXlm } from '../config'

interface AccountData {
  public_key: string
  credits: number | string
  earnings: number | string
  search_price: number | string
}

function WalletPage() {
  const { connected, publicKey, canSign, connect, signXdr } = useWallet()
  const [account, setAccount] = useState<AccountData | null>(null)
  const [depositAmount, setDepositAmount] = useState('5')
  const [refundAmount, setRefundAmount] = useState('1')
  const [busy, setBusy] = useState<string | null>(null)
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null)

  const refresh = useCallback(async () => {
    if (!publicKey) return
    try {
      const data = (await api.account(publicKey)) as AccountData
      setAccount(data)
    } catch (err) {
      console.error('account fetch failed', err)
    }
  }, [publicKey])

  useEffect(() => {
    refresh()
  }, [refresh])

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label)
    setMsg(null)
    try {
      await fn()
      setMsg({ kind: 'ok', text: `${label} confirmed on-chain.` })
      await refresh()
    } catch (err) {
      setMsg({ kind: 'err', text: err instanceof Error ? err.message : `${label} failed` })
    } finally {
      setBusy(null)
    }
  }

  if (!connected || !publicKey) {
    return (
      <div className="space-y-6">
        <Header />
        <div className="card text-center py-12">
          <Wallet className="w-12 h-12 mx-auto text-dark-200 mb-4" />
          <p className="text-dark-100 mb-4">Connect your wallet to manage credits and earnings.</p>
          <button onClick={connect} className="btn-primary">Connect Wallet</button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Header />

      {!canSign && (
        <div className="card border-yellow-600/40 bg-yellow-600/10 text-yellow-300 text-sm">
          Read-only demo mode (manual key). Install Freighter to deposit / withdraw.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Stat icon={Coins} label="Search Credits" value={`${toXlm(account?.credits ?? 0)} XLM`} accent />
        <Stat icon={ArrowUpFromLine} label="Earnings (withdrawable)" value={`${toXlm(account?.earnings ?? 0)} XLM`} />
        <Stat icon={Wallet} label="Price / Search" value={`${toXlm(account?.search_price ?? 0)} XLM`} />
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-dark-200 truncate">Account: {publicKey}</p>
        <button onClick={refresh} className="btn-secondary text-sm flex items-center gap-2">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {msg && (
        <div className={`card text-sm ${msg.kind === 'ok' ? 'border-green-600/40 text-green-300' : 'border-red-600/40 text-red-300'}`}>
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Deposit */}
        <div className="card space-y-3">
          <h3 className="font-semibold flex items-center gap-2"><ArrowDownToLine className="w-5 h-5 text-stellar-400" /> Add Credit</h3>
          <p className="text-sm text-dark-200">Deposit XLM to pay for searches.</p>
          <div className="flex gap-2">
            <input type="number" min="0" step="0.1" value={depositAmount}
              onChange={e => setDepositAmount(e.target.value)} className="input-field" />
            <button disabled={!canSign || !!busy} onClick={() => run('Deposit', () => soroban.deposit(publicKey, signXdr, depositAmount))}
              className="btn-primary whitespace-nowrap">
              {busy === 'Deposit' ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Deposit'}
            </button>
          </div>
        </div>

        {/* Refund credits */}
        <div className="card space-y-3">
          <h3 className="font-semibold flex items-center gap-2"><ArrowUpFromLine className="w-5 h-5 text-stellar-400" /> Refund Credit</h3>
          <p className="text-sm text-dark-200">Withdraw unspent credit back to your wallet.</p>
          <div className="flex gap-2">
            <input type="number" min="0" step="0.1" value={refundAmount}
              onChange={e => setRefundAmount(e.target.value)} className="input-field" />
            <button disabled={!canSign || !!busy} onClick={() => run('Refund', () => soroban.withdrawCredits(publicKey, signXdr, refundAmount))}
              className="btn-secondary whitespace-nowrap">
              {busy === 'Refund' ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Refund'}
            </button>
          </div>
        </div>
      </div>

      {/* Withdraw earnings */}
      <div className="card flex items-center justify-between">
        <div>
          <h3 className="font-semibold">Withdraw Earnings</h3>
          <p className="text-sm text-dark-200">Claim what you earned when your knowledge answered searches.</p>
        </div>
        <button disabled={!canSign || !!busy || !Number(account?.earnings)} onClick={() => run('Withdraw', () => soroban.withdraw(publicKey, signXdr))}
          className="btn-primary flex items-center gap-2">
          {busy === 'Withdraw' ? <Loader2 className="w-5 h-5 animate-spin" /> : <><ArrowUpFromLine className="w-4 h-4" /> Withdraw {toXlm(account?.earnings ?? 0)} XLM</>}
        </button>
      </div>
    </div>
  )
}

function Header() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-1">Wallet & Earnings</h1>
      <p className="text-dark-200">Fund searches, and claim earnings when your knowledge gets used.</p>
    </div>
  )
}

function Stat({ icon: Icon, label, value, accent }: { icon: React.ElementType; label: string; value: string; accent?: boolean }) {
  return (
    <div className={`card ${accent ? 'border-stellar-600/30' : ''}`}>
      <div className="flex items-center gap-2 text-dark-200 text-sm mb-2">
        <Icon className="w-4 h-4" /> {label}
      </div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  )
}

export default WalletPage
