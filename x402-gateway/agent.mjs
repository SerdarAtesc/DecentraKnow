// Autonomous agent demo (CLI) — pays per query via x402, no human in the loop.
// Usage: node agent.mjs "your query"   (or runs a built-in demo loop)
import 'dotenv/config'
import { runAgentSearch } from './agent-core.mjs'

const { AGENT_SECRET, GATEWAY_URL = 'http://localhost:4021', NETWORK = 'stellar:testnet' } = process.env
if (!AGENT_SECRET) {
  console.error('Missing AGENT_SECRET in .env (run setup-agent.py).')
  process.exit(1)
}

const queries = process.argv.slice(2)
const demo = queries.length ? queries : [
  'how does proof of work secure bitcoin',
  'what are zero knowledge proofs',
]

for (const q of demo) {
  console.log(`\n🔎 "${q}"`)
  try {
    const r = await runAgentSearch(q, { agentSecret: AGENT_SECRET, gatewayUrl: GATEWAY_URL, network: NETWORK })
    for (const s of r.steps) console.log(`  • ${s.label}: ${s.detail}${s.txUrl ? ' → ' + s.txUrl : ''}`)
    if (r.answer) console.log(`  💡 ${r.answer}`)
    if (r.owners?.length) console.log(`  💰 creators: ${r.owners.map((o) => o.slice(0, 6) + '…').join(', ')}`)
  } catch (e) {
    console.error(`  error:`, e.message ?? e)
  }
}
