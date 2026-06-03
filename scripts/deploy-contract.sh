#!/bin/bash
set -e

echo "=== DecentraKnow - Soroban Contract Deployment ==="

NETWORK="${STELLAR_NETWORK:-testnet}"
RPC_URL="${STELLAR_RPC_URL:-https://soroban-testnet.stellar.org}"
NETWORK_PASSPHRASE="Test SDF Network ; September 2015"

# Payment token (Stellar Asset Contract address) the contract charges in.
# Defaults to the native XLM SAC, derived from the network so it's always correct.
# Override with PAYMENT_TOKEN to charge in another asset (e.g. a USDC SAC).
PAYMENT_TOKEN="${PAYMENT_TOKEN:-$(stellar contract id asset --asset native --network "$NETWORK")}"
# Per-search price in the token's smallest unit (7-decimal USDC: 1 USDC = 10000000).
SEARCH_PRICE="${SEARCH_PRICE:-10000000}"
# Platform share of each search fee, in basis points (3000 = 30%).
PLATFORM_BPS="${PLATFORM_BPS:-3000}"

echo "Network: $NETWORK"
echo "RPC: $RPC_URL"
echo "Payment token: $PAYMENT_TOKEN"
echo "Search price: $SEARCH_PRICE  Platform bps: $PLATFORM_BPS"

cd "$(dirname "$0")/../contracts/knowledge-registry"

echo "Building contract..."
stellar contract build

# stellar-cli 26+ targets wasm32v1-none; older toolchains used wasm32-unknown-unknown.
WASM_PATH="target/wasm32v1-none/release/knowledge_registry.wasm"
if [ ! -f "$WASM_PATH" ]; then
    WASM_PATH="target/wasm32-unknown-unknown/release/knowledge_registry.wasm"
fi

if [ ! -f "$WASM_PATH" ]; then
    echo "ERROR: WASM file not found (looked in target/wasm32v1-none and target/wasm32-unknown-unknown)"
    exit 1
fi

echo "Deploying contract to $NETWORK..."
CONTRACT_ID=$(stellar contract deploy \
    --wasm "$WASM_PATH" \
    --source "$STELLAR_SECRET_KEY" \
    --rpc-url "$RPC_URL" \
    --network-passphrase "$NETWORK_PASSPHRASE")

echo ""
echo "Contract deployed successfully!"
echo "CONTRACT_ID=$CONTRACT_ID"
echo ""
echo "Add this to your backend/.env:"
echo "CONTRACT_ID=$CONTRACT_ID"

echo "Initializing contract..."
stellar contract invoke \
    --id "$CONTRACT_ID" \
    --source "$STELLAR_SECRET_KEY" \
    --rpc-url "$RPC_URL" \
    --network-passphrase "$NETWORK_PASSPHRASE" \
    -- initialize \
    --admin "$STELLAR_PUBLIC_KEY" \
    --payment_token "$PAYMENT_TOKEN" \
    --search_price "$SEARCH_PRICE" \
    --platform_bps "$PLATFORM_BPS"

echo "Contract initialized!"
