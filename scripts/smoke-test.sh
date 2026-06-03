#!/bin/bash
# End-to-end smoke test against the deployed contract on testnet.
# Requires: STELLAR_SECRET_KEY (env), CONTRACT_ID (env or arg 1).
set -e

CID="${1:-$CONTRACT_ID}"
SK="$STELLAR_SECRET_KEY"
RPC="${STELLAR_RPC_URL:-https://soroban-testnet.stellar.org}"
NP="Test SDF Network ; September 2015"
PK="$STELLAR_PUBLIC_KEY"

inv() { stellar contract invoke --id "$CID" --source "$SK" --rpc-url "$RPC" --network-passphrase "$NP" -- "$@"; }

# 32-byte hex test values.
ZERO=$(printf '00%.0s' {1..32})            # all zeros
QUERY=$(printf '00%.0s' {1..31})01         # 31 zero bytes + 0x01 -> Hamming 1 from ZERO
FF=$(printf 'ff%.0s' {1..32})              # all ones -> Hamming 256 from ZERO
CA=$(printf '01%.0s' {1..32})
CB=$(printf '02%.0s' {1..32})
EA=$(printf '0a%.0s' {1..32})
EB=$(printf '0b%.0s' {1..32})

echo "Contract: $CID"
echo "Admin/Owner/Payer: $PK"
echo

echo "1) register A (sim_hash = ZERO)"
inv register_knowledge --owner "$PK" --content_hash "$CA" --embedding_hash "$EA" --sim_hash "$ZERO" --manifest_cid "QmA" --source_url "https://a.example"
echo "2) register B (sim_hash = FF)"
inv register_knowledge --owner "$PK" --content_hash "$CB" --embedding_hash "$EB" --sim_hash "$FF" --manifest_cid "QmB" --source_url "https://b.example"

echo "3) get_record_count"; inv get_record_count
echo "4) search (query Hamming 1 from A, 255 from B) -> expect A(id 0,dist 1) first"
inv search --query "$QUERY" --top_k 2

echo "5) deposit 5 XLM (50000000 stroops)"; inv deposit --from "$PK" --amount 50000000
echo "6) get_credits"; inv get_credits --user "$PK"

echo "7) pay_search (payer, result_ids=[0]) -> charges 1 XLM, splits"
inv pay_search --payer "$PK" --result_ids '[0]'
echo "8) get_credits after pay -> expect 40000000"; inv get_credits --user "$PK"
echo "9) get_earnings (owner==admin==payer here, so full price accrues)"; inv get_earnings --user "$PK"

echo "10) withdraw earnings"; inv withdraw --to "$PK"
echo "11) get_earnings after withdraw -> expect 0"; inv get_earnings --user "$PK"

echo "12) withdraw_credits: refund 2 XLM of unspent credit -> expect remaining 20000000"
inv withdraw_credits --to "$PK" --amount 20000000
echo "13) get_credits after refund -> expect 20000000"; inv get_credits --user "$PK"

echo; echo "✅ Smoke test sequence complete."
