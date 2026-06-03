import { useState } from 'react'
import { Search, Loader2, Coins, CheckCircle2, Trophy, Zap, Sparkles } from 'lucide-react'
import { useWallet } from '../hooks/useWallet'
import { api } from '../services/api'
import { toXlm } from '../config'

interface PaidResult {
  record_id: number
  distance: number
  content_hash: string
  title: string
  content_preview: string
  owner: string
  ipfs_cid: string
}

interface EarningEntry {
  owner: string
  amount: number | string
}

interface PaidSearchData {
  results: PaidResult[]
  query: string
  answer: string | null
  payment: {
    charged: boolean
    tx_hash: string | null
    price: number | string
    platform_cut: number | string
    owner_earnings: EarningEntry[]
  }
  message: string
}

const short = (pk: string) => (pk ? `${pk.slice(0, 6)}…${pk.slice(-4)}` : '—')

function PaidSearchPage() {
  const { connected, publicKey, connect } = useWallet()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<PaidSearchData | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || !publicKey) return
    setLoading(true)
    setError(null)
    setData(null)
    try {
      const res = (await api.paidSearch({ query, payer: publicKey, top_k: 5 })) as PaidSearchData
      setData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
          <Zap className="w-6 h-6 text-stellar-400" /> Paid On-Chain Search
        </h1>
        <p className="text-dark-200">
          Ranking runs <span className="text-stellar-400">inside the smart contract</span> (Hamming distance over
          SimHashes). Each search pays the owners whose knowledge answered it.
        </p>
      </div>

      {!connected ? (
        <div className="card text-center py-10">
          <p className="text-dark-100 mb-4">Connect a wallet to pay for searches.</p>
          <button onClick={connect} className="btn-primary">Connect Wallet</button>
        </div>
      ) : (
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-200" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ask the network… (charged from your credit)"
              className="input-field pl-12"
            />
          </div>
          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Search & Pay'}
          </button>
        </form>
      )}

      {error && <div className="card border-red-600/40 text-red-300 text-sm">{error}</div>}

      {data && (
        <div className="space-y-5">
          {/* Synthesized answer (RAG over the on-chain-ranked sources) */}
          {data.answer && (
            <div className="card border-stellar-600/30 space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <Sparkles className="w-5 h-5 text-stellar-400" /> Answer
              </div>
              <p className="text-dark-100 whitespace-pre-wrap leading-relaxed">{data.answer}</p>
              <p className="text-xs text-dark-200 pt-1">
                Synthesized from the {data.results.length} sources below — whose owners were just paid.
              </p>
            </div>
          )}

          {/* Payment receipt */}
          <div className="card border-stellar-600/30 space-y-3">
            <div className="flex items-center gap-2 font-semibold">
              {data.payment.charged ? (
                <CheckCircle2 className="w-5 h-5 text-green-400" />
              ) : (
                <Coins className="w-5 h-5 text-yellow-400" />
              )}
              {data.payment.charged ? 'Search settled on-chain' : 'Not charged'}
            </div>
            <p className="text-sm text-dark-200">{data.message}</p>

            {data.payment.charged && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
                <Mini label="Paid" value={`${toXlm(data.payment.price)} XLM`} />
                <Mini label="Platform" value={`${toXlm(data.payment.platform_cut)} XLM`} />
                <Mini label="To owners" value={`${data.payment.owner_earnings.length} paid`} />
              </div>
            )}

            {data.payment.owner_earnings.length > 0 && (
              <div className="space-y-1 pt-1">
                {data.payment.owner_earnings.map(e => (
                  <div key={e.owner} className="flex items-center justify-between text-sm bg-dark-700/50 rounded-lg px-3 py-2">
                    <span className="flex items-center gap-2 text-dark-100">
                      <Trophy className="w-4 h-4 text-stellar-400" /> {short(e.owner)}
                      {e.owner === publicKey && <span className="text-xs text-stellar-400">(you)</span>}
                    </span>
                    <span className="text-green-300 font-medium">+{toXlm(e.amount)} XLM</span>
                  </div>
                ))}
              </div>
            )}
            {data.payment.tx_hash && (
              <a
                className="text-xs text-stellar-400 hover:underline"
                href={`https://stellar.expert/explorer/testnet/tx/${data.payment.tx_hash}`}
                target="_blank"
                rel="noreferrer"
              >
                View transaction ↗
              </a>
            )}
          </div>

          {/* Ranked results = the sources */}
          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-dark-100">Sources · ranked on-chain by Hamming distance</h3>
            {data.results.map((r, idx) => (
              <div key={r.record_id} className="card hover:border-stellar-600/30 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs bg-stellar-600/20 text-stellar-400 px-2 py-0.5 rounded">#{idx + 1}</span>
                      <h3 className="font-semibold">{r.title || 'Untitled'}</h3>
                    </div>
                    <p className="text-sm text-dark-100 line-clamp-2">{r.content_preview}</p>
                    <p className="text-xs text-dark-200 mt-2">owner {short(r.owner)} · record #{r.record_id}</p>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-dark-200">Hamming</div>
                    <div className="text-lg font-bold text-stellar-400">{r.distance}</div>
                  </div>
                </div>
              </div>
            ))}
            {data.results.length === 0 && (
              <div className="card text-center text-dark-200 py-8">No records matched on-chain.</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-dark-700/50 rounded-lg px-3 py-2">
      <div className="text-dark-200 text-xs">{label}</div>
      <div className="font-semibold">{value}</div>
    </div>
  )
}

export default PaidSearchPage
