"""
One-time setup for the x402 agent demo (fully automated — no web faucet):
  1. generate/reuse an agent keypair (persisted to x402-gateway/.env as AGENT_SECRET)
  2. friendbot-fund it with XLM
  3. add a USDC trustline
  4. swap XLM -> ~5 USDC via a testnet DEX path payment
  5. add a USDC trustline to the payTo account (admin) so it can receive x402 payments

Run from repo root:  backend/venv/bin/python x402-gateway/setup-agent.py
"""
import os
import re
import httpx
from pathlib import Path
from stellar_sdk import Keypair, Server, TransactionBuilder, Network, Asset

ROOT = Path(__file__).resolve().parent.parent
GW_ENV = ROOT / "x402-gateway" / ".env"
BK_ENV = ROOT / "backend" / ".env"

HORIZON = "https://horizon-testnet.stellar.org"
PASSPHRASE = Network.TESTNET_NETWORK_PASSPHRASE
USDC = Asset("USDC", "GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5")
server = Server(HORIZON)


def env_get(path, key):
    m = re.search(rf"^{key}=(.*)$", path.read_text(), re.M)
    return m.group(1).strip() if m else None


def env_set(path, key, val):
    txt = path.read_text()
    if re.search(rf"^{key}=", txt, re.M):
        txt = re.sub(rf"^{key}=.*$", f"{key}={val}", txt, flags=re.M)
    else:
        txt += f"\n{key}={val}\n"
    path.write_text(txt)


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
        return None  # no account
    for b in acc["balances"]:
        if b.get("asset_code") == "USDC" and b.get("asset_issuer") == USDC.issuer:
            return float(b["balance"])
    return None  # no trustline


def submit(kp, build):
    src = server.load_account(kp.public_key)
    tb = TransactionBuilder(src, network_passphrase=PASSPHRASE, base_fee=200)
    build(tb)
    tx = tb.set_timeout(60).build()
    tx.sign(kp)
    return server.submit_transaction(tx)


def main():
    # 1) agent keypair
    secret = env_get(GW_ENV, "AGENT_SECRET")
    if secret and secret.startswith("S") and len(secret) == 56:
        agent = Keypair.from_secret(secret)
        print(f"agent (reused): {agent.public_key}")
    else:
        agent = Keypair.random()
        env_set(GW_ENV, "AGENT_SECRET", agent.secret)
        print(f"agent (new):    {agent.public_key}  -> saved to x402-gateway/.env")

    # 2) friendbot
    if not account_exists(agent.public_key):
        httpx.get(f"https://friendbot.stellar.org/?addr={agent.public_key}", timeout=30)
        print("  friendbot funded with XLM")

    # 3) USDC trustline (agent)
    if usdc_balance(agent.public_key) is None:
        submit(agent, lambda tb: tb.append_change_trust_op(asset=USDC))
        print("  agent USDC trustline added")

    # 4) swap XLM -> USDC if low
    bal = usdc_balance(agent.public_key) or 0.0
    if bal < 1.0:
        submit(
            agent,
            lambda tb: tb.append_path_payment_strict_receive_op(
                destination=agent.public_key,
                send_asset=Asset.native(),
                send_max="50",
                dest_asset=USDC,
                dest_amount="5",
                path=[],
            ),
        )
        print(f"  swapped XLM -> USDC (now {usdc_balance(agent.public_key)} USDC)")
    else:
        print(f"  agent USDC balance: {bal}")

    # 5) payTo (admin) USDC trustline so it can RECEIVE x402 payments
    payto_secret = env_get(BK_ENV, "STELLAR_SECRET_KEY")
    admin = Keypair.from_secret(payto_secret)
    if usdc_balance(admin.public_key) is None:
        submit(admin, lambda tb: tb.append_change_trust_op(asset=USDC))
        print(f"  payTo {admin.public_key[:8]}… USDC trustline added")
    else:
        print(f"  payTo USDC balance: {usdc_balance(admin.public_key)}")

    print("\nDone. Agent ready to pay via x402.")


if __name__ == "__main__":
    main()
