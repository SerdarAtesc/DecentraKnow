import { useState } from 'react'
import {
  Bot, Loader2, CheckCircle2, CircleDollarSign, ExternalLink, Sparkles, Trophy, Brain, Coins,
} from 'lucide-react'
import { shortKey, toUsdc, STELLAR_EXPERT_TX } from '../config'

interface Step { label: string; detail: string; txUrl?: string }
interface Payout { owner: string; amount: number; tx: string }
interface SearchResult {
  query: string
  steps: Step[]
  answer: string | null
  owners: string[]
  txHash?: string
  paid?: { display: string }
  distribution?: { distributed: Payout[] }
}
interface TaskResult {
  task: string
  plan: string[]
  searches: SearchResult[]
  finalAnswer: string | null
  economics: {
    searchCount: number
    totalSpentStroops: number
    creatorsPaidStroops: number
    platformStroops: number
  }
}

const short = shortKey
const usdc = toUsdc
const EXPERT = STELLAR_EXPERT_TX

function AgentPage() {
  const [mode, setMode] = useState<'single' | 'task'>('task')

  // single search
  const [query, setQuery] = useState('zero knowledge proofs')
  const [sLoading, setSLoading] = useState(false)
  const [single, setSingle] = useState<SearchResult | null>(null)

  // ai agent task
  const [task, setTask] = useState('Explain proof of work and how Stellar consensus differs')
  const [tLoading, setTLoading] = useState(false)
  const [result, setResult] = useState<TaskResult | null>(null)

  const [error, setError] = useState<string | null>(null)

  const runSingle = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setSLoading(true); setError(null); setSingle(null)
    try {
      const res = await fetch('/gw/demo/search', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || 'failed')
      setSingle(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent run failed. Is the x402 gateway on :4021?')
    } finally { setSLoading(false) }
  }

  const runTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!task.trim()) return
    setTLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/gw/demo/agent-task', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
      })
      const data = await res.json()
      if (!res.ok || data.error) throw new Error(data.error || 'failed')
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent run failed. Is the x402 gateway on :4021?')
    } finally { setTLoading(false) }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
          <Bot className="w-6 h-6 text-stellar-400" /> Agent API (x402)
        </h1>
        <p className="text-dark-200">
          An autonomous AI agent pays <span className="text-stellar-400">USDC per query</span> via the
          standard x402 protocol — no human, no account, no API key. Its spend flows to the human
          creators of the knowledge it uses.
        </p>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => setMode('task')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg ${mode === 'task' ? 'bg-stellar-600 text-white' : 'bg-dark-600 text-dark-100'}`}
        >
          <Brain className="w-4 h-4" /> AI agent (multi-step)
        </button>
        <button
          onClick={() => setMode('single')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg ${mode === 'single' ? 'bg-stellar-600 text-white' : 'bg-dark-600 text-dark-100'}`}
        >
          <CircleDollarSign className="w-4 h-4" /> Single paid search
        </button>
      </div>

      {error && <div className="card border-red-600/40 text-red-300 text-sm">{error}</div>}

      {/* ---------------- AI agent task mode ---------------- */}
      {mode === 'task' && (
        <>
          <form onSubmit={runTask} className="space-y-3">
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Give the agent a research task… it will plan queries, pay for each, and synthesize an answer."
              className="input-field min-h-[80px] resize-y"
            />
            <button type="submit" disabled={tLoading} className="btn-primary flex items-center gap-2">
              {tLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Brain className="w-5 h-5" />}
              {tLoading ? 'Agent working (planning, paying, synthesizing)…' : 'Run AI agent'}
            </button>
          </form>

          {result && (
            <div className="space-y-5">
              {/* economics */}
              <div className="card border-stellar-600/30 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <Stat icon={Brain} label="Queries" value={String(result.economics.searchCount)} />
                <Stat icon={CircleDollarSign} label="Agent spent" value={usdc(result.economics.totalSpentStroops)} />
                <Stat icon={Trophy} label="Creators earned" value={usdc(result.economics.creatorsPaidStroops)} accent />
                <Stat icon={Coins} label="Platform" value={usdc(result.economics.platformStroops)} />
              </div>

              {/* final answer */}
              {result.finalAnswer && (
                <div className="card border-stellar-600/30 space-y-2">
                  <div className="flex items-center gap-2 font-semibold">
                    <Sparkles className="w-5 h-5 text-stellar-400" /> Agent's answer
                  </div>
                  <p className="text-dark-100 whitespace-pre-wrap leading-relaxed">{result.finalAnswer}</p>
                </div>
              )}

              {/* plan + per-query trace */}
              <div className="card space-y-3">
                <div className="font-semibold flex items-center gap-2">
                  <Brain className="w-5 h-5 text-stellar-400" /> What the agent did
                </div>
                {result.searches.map((s, i) => (
                  <div key={i} className="bg-dark-700/50 rounded-lg px-3 py-2 text-sm space-y-1">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-dark-100">
                        <span className="text-stellar-400">#{i + 1}</span> paid {s.paid?.display} for “{s.query}”
                      </span>
                      {s.txHash && (
                        <a href={`${EXPERT}/${s.txHash}`} target="_blank" rel="noreferrer"
                          className="text-stellar-400 hover:underline inline-flex items-center gap-1 shrink-0">
                          tx <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                    {(s.distribution?.distributed?.length ?? 0) > 0 && (
                      <div className="text-green-300 text-xs">
                        → paid creators: {s.distribution!.distributed.map((d) => `${short(d.owner)} +${usdc(d.amount)}`).join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* ---------------- single search mode ---------------- */}
      {mode === 'single' && (
        <>
          <form onSubmit={runSingle} className="flex gap-3">
            <input value={query} onChange={(e) => setQuery(e.target.value)}
              placeholder="Query the agent will pay for…" className="input-field flex-1" />
            <button type="submit" disabled={sLoading} className="btn-primary whitespace-nowrap flex items-center gap-2">
              {sLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Bot className="w-5 h-5" />}
              {sLoading ? 'Agent paying…' : 'Run agent'}
            </button>
          </form>

          {single && (
            <div className="space-y-5">
              <div className="card space-y-3">
                <div className="font-semibold flex items-center gap-2">
                  <CircleDollarSign className="w-5 h-5 text-stellar-400" /> x402 handshake
                </div>
                <ol className="space-y-2">
                  {single.steps.map((s, i) => (
                    <li key={i} className="flex items-start gap-3 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                      <span>
                        <span className="text-dark-100 font-medium">{s.label}</span>
                        <span className="text-dark-200"> — {s.detail}</span>
                        {s.txUrl && (
                          <a href={s.txUrl} target="_blank" rel="noreferrer"
                            className="text-stellar-400 hover:underline inline-flex items-center gap-1 ml-1">
                            view <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>

              {single.distribution && single.distribution.distributed.length > 0 && (
                <div className="card border-green-600/30 space-y-2">
                  <div className="flex items-center gap-2 font-semibold">
                    <Trophy className="w-5 h-5 text-green-400" /> Creators paid in USDC
                  </div>
                  {single.distribution.distributed.map((d) => (
                    <div key={d.tx} className="flex items-center justify-between text-sm bg-dark-700/50 rounded-lg px-3 py-2">
                      <span className="text-dark-100">{short(d.owner)}</span>
                      <span className="flex items-center gap-3">
                        <span className="text-green-300 font-medium">+{usdc(d.amount)}</span>
                        <a href={`${EXPERT}/${d.tx}`} target="_blank" rel="noreferrer"
                          className="text-stellar-400 hover:underline inline-flex items-center gap-1">
                          tx <ExternalLink className="w-3 h-3" />
                        </a>
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {single.answer && (
                <div className="card border-stellar-600/30 space-y-2">
                  <div className="flex items-center gap-2 font-semibold">
                    <Sparkles className="w-5 h-5 text-stellar-400" /> Answer
                  </div>
                  <p className="text-dark-100 whitespace-pre-wrap leading-relaxed">{single.answer}</p>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function Stat({ icon: Icon, label, value, accent }: { icon: React.ElementType; label: string; value: string; accent?: boolean }) {
  return (
    <div className={accent ? 'text-green-300' : ''}>
      <div className="flex items-center gap-1.5 text-dark-200 text-xs mb-1">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className="text-lg font-bold">{value}</div>
    </div>
  )
}

export default AgentPage
