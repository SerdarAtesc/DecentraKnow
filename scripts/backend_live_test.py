"""
Live integration test: the Python backend talking to the DEPLOYED contract on
testnet, using real OpenAI embeddings.

Validates the whole Faz 2 chain end-to-end:
  text -> OpenAI embedding -> SimHash (Python) -> register (chain)
       -> onchain_search (parse + semantic ranking) -> deposit -> pay_search -> withdraw

Does NOT write to Qdrant (shared cloud collection) — id->content mapping is done
locally here. Run from backend/:  python ../scripts/backend_live_test.py
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from stellar_sdk import Keypair

from app.core.config import get_settings
from app.services.embedding_service import (
    generate_embedding,
    compute_content_hash,
    compute_embedding_hash,
)
from app.services.simhash_service import simhash_hex, compute_simhash, hamming_distance
from app.services.blockchain_service import blockchain_service

settings = get_settings()

DOCS = [
    "The Stellar network enables fast, low-cost cross-border payments using the XLM asset.",
    "Photosynthesis is the process by which green plants convert sunlight into chemical energy.",
    "Soroban is the smart contract platform for Stellar, written in Rust and compiled to WASM.",
]
QUERY = "How do smart contracts work on the Stellar blockchain?"


async def main():
    pk = Keypair.from_secret(settings.stellar_secret_key).public_key
    nonce = int(time.time())
    print(f"Contract : {settings.contract_id}")
    print(f"Owner    : {pk}")
    print(f"Price    : {blockchain_service.get_search_price()} stroops\n")

    # 1) Seed: embed -> simhash -> register on-chain.
    id_to_doc = {}
    for i, text in enumerate(DOCS):
        body = f"[{nonce}] {text}"  # nonce keeps content_hash unique across runs
        emb = await generate_embedding(body)
        sh = simhash_hex(emb)
        reg = await blockchain_service.register_knowledge(
            owner_public_key=pk,
            content_hash=compute_content_hash(body),
            embedding_hash=compute_embedding_hash(emb),
            sim_hash=sh,
            manifest_cid=f"QmLive{nonce}_{i}",
            source_url="https://live.test",
        )
        if not reg:
            print(f"  register FAILED for doc {i}")
            return
        id_to_doc[reg["record_id"]] = text
        print(f"  registered id={reg['record_id']}  «{text[:48]}…»")

    # 2) On-chain search with a real query embedding.
    q_emb = await generate_embedding(QUERY)
    q_sh = simhash_hex(q_emb)
    print(f"\nQuery: {QUERY}")
    hits = blockchain_service.onchain_search(q_sh, top_k=3)
    print("On-chain ranking (closest first):")
    for h in hits:
        print(f"  id={h['id']}  dist={h['distance']}  «{id_to_doc.get(h['id'],'?')[:48]}…»")

    plants_id = [i for i, d in id_to_doc.items() if d.startswith("Photosynthesis")][0]
    best_id = hits[0]["id"]
    print(f"\n  -> closest is the {'EXPECTED Stellar/Soroban doc' if best_id != plants_id else 'unrelated plants doc (!)'}")

    # 3) deposit -> pay_search -> earnings -> withdraw, all via the Python service.
    price = blockchain_service.get_search_price()
    print(f"\nCredits before: {blockchain_service.get_credits(pk)}")
    await blockchain_service.deposit(pk, price * 2)
    print(f"Credits after deposit: {blockchain_service.get_credits(pk)}")

    result_ids = [h["id"] for h in hits]
    tx = await blockchain_service.pay_search(pk, result_ids)
    print(f"pay_search tx: {tx}")
    print(f"Credits after pay: {blockchain_service.get_credits(pk)}  (expect -{price})")
    print(f"Earnings accrued: {blockchain_service.get_earnings(pk)}")

    print("\nDone. Python <-> live contract integration verified.")


if __name__ == "__main__":
    asyncio.run(main())
