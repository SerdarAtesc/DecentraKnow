#!/bin/bash
set -e

echo "=== DecentraKnow - Project Setup ==="

echo ""
echo "[1/4] Setting up backend..."
cd backend
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env.example .env
echo "  Backend ready. Edit backend/.env with your API keys."

echo ""
echo "[2/4] Setting up frontend..."
cd ../frontend
npm install
echo "  Frontend ready."

echo ""
echo "[3/4] Checking Qdrant..."
if command -v docker &> /dev/null; then
    echo "  Starting Qdrant via Docker..."
    docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest 2>/dev/null || echo "  Qdrant already running."
else
    echo "  Docker not found. Install Docker and run: docker run -d -p 6333:6333 qdrant/qdrant"
fi

echo ""
echo "[4/4] Checking Stellar CLI..."
if command -v stellar &> /dev/null; then
    echo "  Stellar CLI found: $(stellar --version)"
else
    echo "  Stellar CLI not found. Install: cargo install --locked stellar-cli"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Add your OPENAI_API_KEY to backend/.env"
echo "  2. Add your STELLAR_SECRET_KEY to backend/.env"
echo "  3. Run: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "  4. Run: cd frontend && npm run dev"
echo "  5. Deploy contract: bash scripts/deploy-contract.sh"
