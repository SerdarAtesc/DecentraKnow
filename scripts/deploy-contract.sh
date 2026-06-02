#!/bin/bash
set -e

echo "=== DecentraKnow - Soroban Contract Deployment ==="

NETWORK="${STELLAR_NETWORK:-testnet}"
RPC_URL="${STELLAR_RPC_URL:-https://soroban-testnet.stellar.org}"
NETWORK_PASSPHRASE="Test SDF Network ; September 2015"

echo "Network: $NETWORK"
echo "RPC: $RPC_URL"

cd "$(dirname "$0")/../contracts/knowledge-registry"

echo "Building contract..."
stellar contract build

WASM_PATH="target/wasm32-unknown-unknown/release/knowledge_registry.wasm"

if [ ! -f "$WASM_PATH" ]; then
    echo "ERROR: WASM file not found at $WASM_PATH"
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
    --admin "$STELLAR_PUBLIC_KEY"

echo "Contract initialized!"
