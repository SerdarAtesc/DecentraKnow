# DecentraKnow x402 Gateway — the agent rail

Makes DecentraKnow's semantic search a **machine-payable API** via the standard
[x402](https://www.x402.org/) protocol on Stellar. An autonomous agent pays **USDC per query**
(real OpenZeppelin facilitator, Stellar testnet) — no human, no account, no API key — and gets an
on-chain-ranked, RAG-synthesized answer.

This is a second payment rail alongside the human UI (which uses XLM credits). The search ranking,
relevance re-rank, and RAG are unchanged; x402 only replaces the payment+access step for agents.

```
agent.mjs ──GET /x402/search──▶ gateway (:4021) ──402 Payment Required (USDC)──▶ agent
agent signs USDC payment, retries with X-Payment
gateway → facilitator /verify + /settle  (USDC moves agent → payTo, fees sponsored)
gateway → FastAPI POST /api/x402/run  (X-Internal-Secret; no payment gate)
        → { results, answer, owners }  ──▶ agent
```

## Setup

```bash
cd x402-gateway
npm install

# Get a free testnet facilitator key (no signup):
curl https://channels.openzeppelin.com/testnet/gen     # -> {"apiKey":"..."}
# Put it in .env as FACILITATOR_API_KEY (see .env.example).

# Fund an agent account automatically (XLM via friendbot, USDC via testnet DEX swap),
# and add a USDC trustline to payTo. Persists AGENT_SECRET into .env:
../backend/venv/bin/python setup-agent.py
```

`.env` keys: `FACILITATOR_API_KEY`, `PAYTO` (G-account that receives USDC, needs a USDC trustline),
`PRICE` (`$0.01`), `FASTAPI_URL`, `X402_INTERNAL_SECRET` (must match `backend/.env`), `AGENT_SECRET`.

## Run

```bash
# 1. backend (repo root)
cd ../backend && source venv/bin/activate && uvicorn app.main:app --port 8000
# 2. gateway
cd ../x402-gateway && node server.mjs
# 3. autonomous agent (pays per query)
node agent.mjs "how does proof of work secure bitcoin"
```

Expected: `402 → signed USDC payment → ✅ settled <stellar.expert tx> → 💡 Answer …`.

## Notes / facts confirmed on testnet
- Testnet USDC SAC: `CBIELTK6YBZJU5UP2WWQEUCYKLPU6AUNZ2BQ4WWFEIE3USCIHMXQDAMA`
  = `USDC:GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5` (7 decimals; `$0.01` = `100000`).
- Facilitator: `https://channels.openzeppelin.com/x402/testnet` — `exact` scheme, fees sponsored
  (the agent needs only USDC, no XLM for gas).
- Packages: `@x402/core`, `@x402/express`, `@x402/stellar` (v2.8). Node ≥ 22.12, ESM.
- **MVP scope:** USDC settles to `payTo` (platform). Per-creator USDC payout (splitting to the result
  owners returned in `owners`) is a stretch — the human XLM rail already does atomic creator payouts.
