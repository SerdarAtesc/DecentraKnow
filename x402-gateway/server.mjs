// DecentraKnow x402 gateway — the "agent rail".
// Fronts the search API with the standard x402 protocol (USDC, Stellar testnet,
// OpenZeppelin facilitator). An autonomous client pays per query; on settlement we
// proxy to the FastAPI payment-free /x402/run endpoint and return the answer.
import 'dotenv/config'
import express from 'express'
import { paymentMiddleware, x402ResourceServer } from '@x402/express'
import { ExactStellarScheme } from '@x402/stellar/exact/server'
import { HTTPFacilitatorClient } from '@x402/core/server'
import { runAgentSearch } from './agent-core.mjs'
import { runAgentTask } from './agent-task.mjs'

const {
  PORT = '4021',
  FACILITATOR_URL = 'https://channels.openzeppelin.com/x402/testnet',
  FACILITATOR_API_KEY,
  PAYTO,
  PRICE = '$0.01',
  NETWORK = 'stellar:testnet',
  FASTAPI_URL = 'http://localhost:8000',
  X402_INTERNAL_SECRET,
} = process.env

for (const [k, v] of Object.entries({ PAYTO, FACILITATOR_API_KEY, X402_INTERNAL_SECRET })) {
  if (!v) {
    console.error(`Missing ${k} in .env (see .env.example)`)
    process.exit(1)
  }
}

// USDC stroops (7-dp) for the configured price, used for per-creator payouts.
const PRICE_STROOPS = Math.round(parseFloat(String(PRICE).replace(/[^0-9.]/g, '')) * 1e7)

const facilitatorClient = new HTTPFacilitatorClient({
  url: FACILITATOR_URL,
  createAuthHeaders: async () => {
    const headers = { Authorization: `Bearer ${FACILITATOR_API_KEY}` }
    return { verify: headers, settle: headers, supported: headers }
  },
})

const x402Server = new x402ResourceServer(facilitatorClient).register(
  NETWORK,
  new ExactStellarScheme(),
)

const app = express()

// Allow the frontend (vite dev) to call the demo route.
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*')
  res.header('Access-Control-Allow-Headers', 'Content-Type')
  res.header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
  if (req.method === 'OPTIONS') return res.sendStatus(204)
  next()
})

app.get('/health', (_req, res) =>
  res.json({ ok: true, service: 'decentraknow-x402-gateway', network: NETWORK, payTo: PAYTO }),
)

// Browser demo: run the autonomous agent flow server-side (it signs with AGENT_SECRET)
// and return the structured 402 → pay → settle → answer handshake for the UI to render.
app.post('/demo/search', express.json(), async (req, res) => {
  const query = (req.body?.query ?? '').toString().trim()
  if (!query) return res.status(400).json({ error: 'missing query' })
  if (!process.env.AGENT_SECRET) return res.status(500).json({ error: 'AGENT_SECRET not configured' })
  try {
    const result = await runAgentSearch(query, {
      agentSecret: process.env.AGENT_SECRET,
      gatewayUrl: `http://localhost:${PORT}`,
      network: NETWORK,
    })
    res.json(result)
  } catch (e) {
    res.status(500).json({ error: 'agent run failed', detail: String(e?.message ?? e) })
  }
})

// x402 paywall on the search resource. Clients without a valid X-Payment get a 402
// with PaymentRequirements; once they pay (USDC, facilitator-settled) the handler runs.
app.use(
  paymentMiddleware(
    {
      'GET /x402/search': {
        accepts: [{ scheme: 'exact', price: PRICE, network: NETWORK, payTo: PAYTO }],
        description: 'DecentraKnow paid semantic search — on-chain ranked + RAG answer',
        mimeType: 'application/json',
      },
    },
    x402Server,
  ),
)

// AI-agent demo: an LLM plans queries, the agent pays for each via x402, the LLM
// synthesizes a final cited answer. Returns the full plan → pay → synthesize trace.
app.post('/demo/agent-task', express.json(), async (req, res) => {
  const task = (req.body?.task ?? '').toString().trim()
  if (!task) return res.status(400).json({ error: 'missing task' })
  if (!process.env.AGENT_SECRET || !process.env.OPENAI_API_KEY) {
    return res.status(500).json({ error: 'AGENT_SECRET / OPENAI_API_KEY not configured' })
  }
  try {
    const result = await runAgentTask(task, {
      agentSecret: process.env.AGENT_SECRET,
      gatewayUrl: `http://localhost:${PORT}`,
      network: NETWORK,
      openaiKey: process.env.OPENAI_API_KEY,
      model: process.env.OPENAI_MODEL || 'gpt-4o-mini',
    })
    res.json(result)
  } catch (e) {
    res.status(500).json({ error: 'agent task failed', detail: String(e?.message ?? e) })
  }
})

// Only reached after payment is settled.
app.get('/x402/search', async (req, res) => {
  const q = (req.query.q ?? '').toString()
  if (!q) return res.status(400).json({ error: 'missing ?q=<query>' })
  const top_k = Number(req.query.top_k ?? 5)
  // fast mode (used by the parallel multi-step agent): don't block the response on the
  // on-chain USDC payout — the backend computes the split now and settles it in the background.
  const fast = req.query.fast === '1' || req.query.fast === 'true'
  try {
    const r = await fetch(`${FASTAPI_URL}/api/x402/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': X402_INTERNAL_SECRET,
      },
      body: JSON.stringify({ query: q, payer: PAYTO, top_k }),
    })
    const data = await r.json()

    // Per-creator USDC payout: split the just-paid amount among the result owners.
    if (data.owners?.length) {
      try {
        const dr = await fetch(`${FASTAPI_URL}/api/x402/distribute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Internal-Secret': X402_INTERNAL_SECRET },
          body: JSON.stringify({ owners: data.owners, amount: PRICE_STROOPS, background: fast }),
        })
        if (dr.ok) data.distribution = await dr.json()
      } catch (e) {
        console.error('distribute failed:', e?.message ?? e)
      }
    }
    res.status(r.status).json(data)
  } catch (e) {
    res.status(502).json({ error: 'search backend unavailable', detail: String(e) })
  }
})

app.listen(Number(PORT), () =>
  console.log(`x402 gateway listening on :${PORT} — network ${NETWORK}, payTo ${PAYTO}`),
)
