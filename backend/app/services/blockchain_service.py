"""
Stellar/Soroban blockchain service for the paid on-chain search registry.

References:
- Stellar SDK: stellar-sdk v11 (Python)
- Network: testnet by default; payment asset is native XLM (Stellar hackathon).
- Only hashes + the 256-bit SimHash are stored on-chain, never embeddings.

Auth model (important):
- `pay_search` is settled by the contract admin == the backend's STELLAR_PUBLIC_KEY,
  signed with STELLAR_SECRET_KEY. This is why no per-search wallet prompt is needed.
- `register_knowledge` requires the *owner* to authorize. In backend-only mode the
  backend signs, so the owner must be the backend's own public key. Real per-user
  ownership (and `deposit`/`withdraw`) is wallet-signed from the frontend (Phase 3).
- `search` and `get_record` are read-only: simulated, never submitted -> zero fee.
"""

from stellar_sdk import (
    Keypair,
    SorobanServer,
    TransactionBuilder,
    scval,
)
from stellar_sdk.soroban_rpc import GetTransactionStatus
from app.core.config import get_settings
import time

settings = get_settings()


class BlockchainService:
    def __init__(self):
        self.server = SorobanServer(settings.stellar_rpc_url)
        self.network_passphrase = settings.stellar_network_passphrase
        self.contract_id = settings.contract_id
        self._keypair: Keypair | None = None

    @property
    def keypair(self) -> Keypair:
        if self._keypair is None:
            if not settings.stellar_secret_key:
                raise ValueError("STELLAR_SECRET_KEY not configured")
            self._keypair = Keypair.from_secret(settings.stellar_secret_key)
        return self._keypair

    @property
    def admin_public_key(self) -> str:
        return self.keypair.public_key

    # ------------------------------------------------------------------
    # low-level helpers
    # ------------------------------------------------------------------

    def _build_tx(self, function_name: str, parameters: list):
        source_account = self.server.load_account(self.keypair.public_key)
        builder = TransactionBuilder(
            source_account=source_account,
            network_passphrase=self.network_passphrase,
            base_fee=100_000,
        )
        builder.append_invoke_contract_function_op(
            contract_id=self.contract_id,
            function_name=function_name,
            parameters=parameters,
        )
        return builder.set_timeout(300).build()

    def _simulate_native(self, function_name: str, parameters: list):
        """Read-only call: simulate and return the native (decoded) return value.

        Costs nothing — never submitted to the network.
        """
        tx = self._build_tx(function_name, parameters)
        sim = self.server.simulate_transaction(tx)
        if sim.error:
            raise Exception(f"Simulation failed for {function_name}: {sim.error}")
        if not sim.results:
            return None
        return scval.to_native(sim.results[0].xdr)

    def _invoke_tx(self, function_name: str, parameters: list) -> dict:
        """State-changing call: simulate, prepare, sign, submit, poll.

        Returns {"tx_hash": str, "result": <native return value or None>}.
        """
        tx = self._build_tx(function_name, parameters)

        sim = self.server.simulate_transaction(tx)
        if sim.error:
            raise Exception(f"Simulation failed for {function_name}: {sim.error}")

        result_native = None
        if sim.results and sim.results[0].xdr:
            result_native = scval.to_native(sim.results[0].xdr)

        tx = self.server.prepare_transaction(tx, sim)
        tx.sign(self.keypair)
        send_resp = self.server.send_transaction(tx)
        if send_resp.status == "ERROR":
            raise Exception(f"Transaction submission failed for {function_name}")

        tx_hash = send_resp.hash
        for _ in range(30):
            time.sleep(1)
            get_resp = self.server.get_transaction(tx_hash)
            if get_resp.status == GetTransactionStatus.SUCCESS:
                return {"tx_hash": tx_hash, "result": result_native}
            if get_resp.status == GetTransactionStatus.FAILED:
                raise Exception(f"Transaction failed on-chain for {function_name}")

        return {"tx_hash": tx_hash, "result": result_native}

    # ------------------------------------------------------------------
    # contract calls
    # ------------------------------------------------------------------

    async def register_knowledge(
        self,
        owner_public_key: str,
        content_hash: str,
        embedding_hash: str,
        sim_hash: str,
        manifest_cid: str,
        source_url: str,
    ) -> dict | None:
        """Register a record on-chain. Returns {"tx_hash", "record_id"} or None."""
        if not self.contract_id:
            return None
        try:
            res = self._invoke_tx(
                "register_knowledge",
                [
                    scval.to_address(owner_public_key),
                    scval.to_bytes(bytes.fromhex(content_hash)),
                    scval.to_bytes(bytes.fromhex(embedding_hash)),
                    scval.to_bytes(bytes.fromhex(sim_hash)),
                    scval.to_string(manifest_cid),
                    scval.to_string(source_url or ""),
                ],
            )
            return {"tx_hash": res["tx_hash"], "record_id": res["result"]}
        except Exception as e:
            print(f"[Blockchain] register_knowledge failed: {e}")
            return None

    def onchain_search(self, query_sim_hash: str, top_k: int) -> list[dict]:
        """Verifiable on-chain ranking by Hamming distance. Read-only (free).

        Returns a list of {"id": int, "distance": int} ordered closest-first.
        """
        if not self.contract_id:
            return []
        try:
            hits = self._simulate_native(
                "search",
                [
                    scval.to_bytes(bytes.fromhex(query_sim_hash)),
                    scval.to_uint32(top_k),
                ],
            )
            # SearchHit struct -> dict {"id":..., "distance":...}
            return [{"id": h["id"], "distance": h["distance"]} for h in (hits or [])]
        except Exception as e:
            print(f"[Blockchain] onchain_search failed: {e}")
            return []

    def get_record(self, record_id: int) -> dict | None:
        """Read a record by its on-chain id (read-only)."""
        if not self.contract_id:
            return None
        try:
            return self._simulate_native("get_record", [scval.to_uint32(record_id)])
        except Exception as e:
            print(f"[Blockchain] get_record failed: {e}")
            return None

    async def deposit(self, from_public_key: str, amount: int) -> str | None:
        """Fund search credit. Signed by `from`; in backend mode `from` must be the
        backend key (real user deposits are wallet-signed from the frontend)."""
        if not self.contract_id:
            return None
        try:
            res = self._invoke_tx(
                "deposit",
                [scval.to_address(from_public_key), scval.to_int128(amount)],
            )
            return res["tx_hash"]
        except Exception as e:
            print(f"[Blockchain] deposit failed: {e}")
            return None

    async def pay_search(self, payer_public_key: str, result_ids: list[int]) -> str | None:
        """Settle a search: deduct the fee from `payer`'s credit and split it among
        the result owners + platform. Signed by the admin (backend). Returns tx hash.
        """
        if not self.contract_id or not result_ids:
            return None
        try:
            res = self._invoke_tx(
                "pay_search",
                [
                    scval.to_address(payer_public_key),
                    scval.to_vec([scval.to_uint32(i) for i in result_ids]),
                ],
            )
            return res["tx_hash"]
        except Exception as e:
            print(f"[Blockchain] pay_search failed: {e}")
            return None

    def get_credits(self, user_public_key: str) -> int:
        if not self.contract_id:
            return 0
        try:
            return self._simulate_native("get_credits", [scval.to_address(user_public_key)]) or 0
        except Exception as e:
            print(f"[Blockchain] get_credits failed: {e}")
            return 0

    def get_earnings(self, user_public_key: str) -> int:
        if not self.contract_id:
            return 0
        try:
            return self._simulate_native("get_earnings", [scval.to_address(user_public_key)]) or 0
        except Exception as e:
            print(f"[Blockchain] get_earnings failed: {e}")
            return 0

    def get_search_price(self) -> int:
        if not self.contract_id:
            return 0
        try:
            return self._simulate_native("get_search_price", []) or 0
        except Exception as e:
            print(f"[Blockchain] get_search_price failed: {e}")
            return 0

    def get_platform_bps(self) -> int:
        if not self.contract_id:
            return 3000
        try:
            return self._simulate_native("get_platform_bps", []) or 3000
        except Exception as e:
            print(f"[Blockchain] get_platform_bps failed: {e}")
            return 3000


blockchain_service = BlockchainService()
