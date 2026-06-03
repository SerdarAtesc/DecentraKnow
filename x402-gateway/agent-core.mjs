// Shared autonomous-agent x402 flow, used by both the CLI (agent.mjs) and the
// gateway's /demo/search route (so the browser can trigger it). Returns structured
// steps so a UI can render the 402 → pay → settle → answer handshake.
import { x402Client, x402HTTPClient } from '@x402/core/client'
import { createEd25519Signer } from '@x402/stellar'
import { ExactStellarScheme } from '@x402/stellar/exact/client'

const EXPERT_TX = 'https://stellar.expert/explorer/testnet/tx'

function buildClient(agentSecret, network) {
  const signer = createEd25519Signer(agentSecret, network)
  const core = new x402Client().register('stellar:*', new ExactStellarScheme(signer))
  return new x402HTTPClient(core)
}

const fmtUsdc = (amount) => `${(Number(amount) / 1e7).toFixed(2)} USDC`

/**
 * Run one autonomous paid search. Returns
 * { ok, query, steps:[{label,detail,txUrl?}], answer, owners, results, txHash, paid }.
 */
export async function runAgentSearch(query, { agentSecret, gatewayUrl, network = 'stellar:testnet', fast = false }) {
  const client = buildClient(agentSecret, network)
  const url = `${gatewayUrl}/x402/search?q=${encodeURIComponent(query)}${fast ? '&fast=1' : ''}`
  const steps = []

  const first = await fetch(url)
  steps.push({ label: 'Request', detail: `GET /x402/search?q=${query}` })

  if (first.status !== 402) {
    const body = await first.json().catch(() => ({}))
    return { ok: true, query, steps, ...body, free: true }
  }

  const required = client.getPaymentRequiredResponse((n) => first.headers.get(n), await first.json())
  const a = required.accepts[0]
  steps.push({
    label: '402 Payment Required',
    detail: `Pay ${fmtUsdc(a.amount)} to ${a.payTo.slice(0, 6)}…${a.payTo.slice(-4)} (${a.network})`,
  })

  const payload = await client.createPaymentPayload(required)
  const headers = client.encodePaymentSignatureHeader(payload)
  steps.push({ label: 'Signed payment', detail: 'Agent autonomously signed a USDC authorization' })

  const paid = await fetch(url, { headers })
  if (!paid.ok) {
    const text = await paid.text()
    steps.push({ label: 'Payment failed', detail: `${paid.status}: ${text}` })
    return { ok: false, query, steps }
  }

  const settle = client.getPaymentSettleResponse((n) => paid.headers.get(n))
  const txHash = settle?.transaction
  steps.push({
    label: 'Settled on-chain',
    detail: txHash ? `tx ${txHash.slice(0, 10)}…` : 'settled',
    txUrl: txHash ? `${EXPERT_TX}/${txHash}` : undefined,
  })

  const data = await paid.json()

  const dist = data.distribution
  if (dist?.distributed?.length) {
    steps.push({
      label: 'Creators paid (USDC)',
      detail: dist.distributed
        .map((d) => `${d.owner.slice(0, 6)}… +${fmtUsdc(d.amount)}`)
        .join(', '),
    })
  } else if (dist) {
    steps.push({ label: 'Creator payout', detail: 'no payable creator (no USDC trustline); kept by platform' })
  }
  steps.push({ label: 'Answer delivered', detail: data.answer ? 'RAG answer returned' : 'no answer' })

  return {
    ok: true,
    query,
    steps,
    answer: data.answer ?? null,
    owners: data.owners ?? [],
    results: data.results ?? [],
    distribution: dist ?? null,
    txHash,
    paid: { amount: a.amount, asset: a.asset, payTo: a.payTo, network: a.network, display: fmtUsdc(a.amount) },
  }
}
