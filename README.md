# DecentraKnow

**Decentralized AI Knowledge Network**

A production-grade system combining AI embeddings, semantic search, RAG (Retrieval Augmented Generation), IPFS decentralized storage, and Stellar blockchain (Soroban smart contracts) to create a verified, AI-native knowledge engine.

## Architecture

```
content → embedding → vector database → IPFS storage → blockchain registry → AI retrieval
```

| Layer | Technology | Purpose |
|-------|-----------|---------|
| AI | OpenAI text-embedding-3-small | Semantic embeddings & LLM reasoning |
| Vector DB | Qdrant | Cosine similarity search with metadata filtering |
| Storage | IPFS (Kubo) | Decentralized content persistence |
| Blockchain | Stellar Soroban | Ownership proof & integrity verification |
| Backend | FastAPI (Python) | API orchestration |
| Frontend | React + Vite + Tailwind | Modern UI with wallet integration |

## Project Structure

```
DecentraKnow/
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── api/           # Route handlers
│   │   ├── core/          # Configuration
│   │   ├── models/        # Pydantic schemas
│   │   └── services/      # Business logic
│   ├── Dockerfile
│   └── requirements.txt
├── contracts/             # Soroban smart contracts (Rust)
│   └── knowledge-registry/
│       └── src/lib.rs
├── frontend/              # React application
│   ├── src/
│   │   ├── components/    # Shared UI components
│   │   ├── pages/         # Route pages
│   │   ├── services/      # API client
│   │   └── hooks/         # Custom React hooks
│   ├── Dockerfile
│   └── package.json
├── docker/                # Docker Compose orchestration
├── scripts/               # Setup & deployment scripts
└── external/              # Reference documentation
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload text or URL → embed → store → register |
| POST | `/api/search` | Semantic search with metadata filters |
| POST | `/api/rag` | RAG query with source attribution |
| POST | `/api/embed` | Generate embedding vector for text |
| POST | `/api/fetch-url` | Scrape and extract webpage content |
| GET | `/api/render` | 2D PCA projection of embedding space |
| GET | `/health` | Service health check |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (for Qdrant and IPFS)
- Rust + `stellar-cli` (for smart contract deployment)
- OpenAI API key
- Stellar testnet account

### Setup

```bash
# Clone and setup
bash scripts/setup.sh

# Or manually:
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your keys

# Frontend
cd frontend
npm install

# Infrastructure
docker compose -f docker/docker-compose.yml up -d qdrant ipfs
```

### Run Development

```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Deploy Smart Contract

```bash
export STELLAR_SECRET_KEY="S..."
export STELLAR_PUBLIC_KEY="G..."
bash scripts/deploy-contract.sh
```

## Key Features

### Duplicate Detection

1. **Exact duplicate**: SHA-256 content hash comparison
2. **Semantic duplicate**: Cosine similarity > 0.92 threshold

### RAG System

- Query → Embedding → Vector search → Context assembly → LLM answer
- Strict grounding: LLM only uses provided context
- Full source attribution in every response

### Blockchain Registry

Each knowledge record stores on-chain:
- `content_hash` (SHA-256 of raw content)
- `embedding_hash` (SHA-256 of embedding vector)
- `manifest_cid` (IPFS CID of full manifest)
- `owner` (Stellar address)
- `timestamp` (ledger time)

Embeddings are NEVER stored on-chain — only hashes for verification.

## Configuration

All configuration via environment variables (see `backend/.env.example`):

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and LLM |
| `QDRANT_HOST` | Qdrant vector DB host |
| `STELLAR_RPC_URL` | Soroban RPC endpoint |
| `CONTRACT_ID` | Deployed smart contract ID |
| `STELLAR_SECRET_KEY` | Signing key for blockchain transactions |
| `SIMILARITY_THRESHOLD` | Semantic duplicate threshold (default: 0.92) |

## License

MIT
