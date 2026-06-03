"""
Create a few funded, USDC-trustlined demo CREATOR accounts and register diverse
content owned by each — so the AI-agent demo shows real, distinct creators earning
USDC no matter what topic is searched (not just the 2 hand-made docs).

Needs the backend running on :8000 (for /upload/prepare + /upload/finalize) and the
stellar CLI (for the creator-signed register). Secrets persist to creators.json.

Run from repo root:  backend/venv/bin/python x402-gateway/setup-creators.py
"""
import json
import re
import subprocess
import httpx
from pathlib import Path
from stellar_sdk import Keypair, Server, TransactionBuilder, Network, Asset

ROOT = Path(__file__).resolve().parent.parent
BK_ENV = ROOT / "backend" / ".env"
CREATORS_FILE = ROOT / "x402-gateway" / "creators.json"

API = "http://localhost:8000/api"
HORIZON = "https://horizon-testnet.stellar.org"
RPC = "https://soroban-testnet.stellar.org"
PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE
USDC = Asset("USDC", "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5")
server = Server(HORIZON)

# Diverse topics, distinct from the existing seed set (avoid the 0.92 dup threshold).
CREATORS = {
    "Ada": [
        ("The Lightning Network", "The Lightning Network is a layer-2 payment protocol on Bitcoin that enables instant, low-fee transactions through bidirectional payment channels settled off-chain.", "blockchain"),
        ("Elliptic Curve Cryptography", "Elliptic curve cryptography secures blockchains using the algebraic structure of elliptic curves over finite fields to create small, fast public and private key pairs.", "blockchain"),
    ],
    "Linus": [
        ("Vector Databases", "Vector databases store high-dimensional embeddings and retrieve them with approximate nearest-neighbor search, powering semantic search and retrieval augmented generation.", "ai"),
        ("Transformer Attention", "The transformer attention mechanism lets a model weigh the relevance of every token to every other token, capturing long-range context across a sequence.", "ai"),
    ],
    "Marie": [
        ("Black Holes", "Black holes are regions of spacetime where gravity is so strong that nothing, not even light, can escape from beyond the event horizon.", "science"),
        ("mRNA Vaccines", "mRNA vaccines teach cells to produce a harmless fragment of a pathogen's protein, triggering an immune response without using the live virus.", "science"),
    ],
    "Kofi": [
        ("Automated Market Makers", "Automated market makers replace order books with liquidity pools and a pricing formula, letting anyone trade tokens permissionlessly on-chain.", "finance"),
        ("Stablecoins", "Stablecoins are cryptocurrencies pegged to a reference asset like the US dollar, combining blockchain settlement with price stability for everyday payments.", "finance"),
    ],
}


def env_get(path, key):
    m = re.search(rf"^{key}=(.*)$", path.read_text(), re.M)
    return m.group(1).strip() if m else None


CID = env_get(BK_ENV, "CONTRACT_ID")


def account_exists(pub):
    try:
        server.load_account(pub)
        return True
    except Exception:
        return False


def usdc_balance(pub):
    try:
        acc = server.accounts().account_id(pub).call()
    except Exception:
        return None
    for b in acc["balances"]:
        if b.get("asset_code") == "USDC" and b.get("asset_issuer") == USDC.issuer:
            return float(b["balance"])
    return None


def submit(kp, build):
    src = server.load_account(kp.public_key)
    tb = TransactionBuilder(src, network_passphrase=PASSPHRASE, base_fee=200)
    build(tb)
    tx = tb.set_timeout(60).build()
    tx.sign(kp)
    server.submit_transaction(tx)


def cli_register(secret, owner, ch, eh, sh, mc):
    out = subprocess.run(
        ["stellar", "contract", "invoke", "--id", CID, "--source", secret,
         "--rpc-url", RPC, "--network-passphrase", PASSPHRASE, "--",
         "register_knowledge", "--owner", owner, "--content_hash", ch,
         "--embedding_hash", eh, "--sim_hash", sh, "--manifest_cid", mc,
         "--source_url", "https://demo.creator"],
        capture_output=True, text=True,
    )
    for line in reversed(out.stdout.strip().splitlines()):
        v = line.strip().strip('"')
        if v.isdigit():
            return v
    return None


def main():
    creators = json.loads(CREATORS_FILE.read_text()) if CREATORS_FILE.exists() else {}

    for name, docs in CREATORS.items():
        secret = creators.get(name)
        kp = Keypair.from_secret(secret) if secret else Keypair.random()
        creators[name] = kp.secret
        CREATORS_FILE.write_text(json.dumps(creators, indent=2))
        print(f"\n=== {name}: {kp.public_key} ===")

        if not account_exists(kp.public_key):
            httpx.get(f"https://friendbot.stellar.org/?addr={kp.public_key}", timeout=30)
            print("  funded (friendbot)")
        if usdc_balance(kp.public_key) is None:
            submit(kp, lambda tb: tb.append_change_trust_op(asset=USDC))
            print("  USDC trustline added")

        for title, content, cat in docs:
            prep = httpx.post(f"{API}/upload/prepare",
                              json={"content": content, "owner": kp.public_key, "title": title, "category": cat},
                              timeout=60).json()
            if prep.get("duplicate"):
                print(f"  skip (dup): {title}")
                continue
            rid = cli_register(kp.secret, kp.public_key, prep["content_hash"],
                               prep["embedding_hash"], prep["sim_hash"], prep["ipfs_cid"])
            if not rid:
                print(f"  FAILED register: {title}")
                continue
            httpx.post(f"{API}/upload/finalize",
                       json={"content_hash": prep["content_hash"], "record_id": int(rid)}, timeout=60)
            print(f"  registered #{rid}: {title}")

    print(f"\nDone. {sum(len(v) for v in CREATORS.values())} docs across {len(CREATORS)} creators. Secrets in creators.json")


if __name__ == "__main__":
    main()
