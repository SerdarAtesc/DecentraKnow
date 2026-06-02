"""
Stellar/Soroban blockchain service for registering knowledge records.

References:
- Stellar SDK: stellar-sdk v11 (Python)
- Network: testnet by default
- RPC URL: https://soroban-testnet.stellar.org
- Only hashes and metadata stored on-chain, never embeddings.
"""

from stellar_sdk import (
    Keypair,
    Network,
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

    async def register_knowledge(
        self,
        owner_public_key: str,
        content_hash: str,
        embedding_hash: str,
        manifest_cid: str,
        source_url: str,
    ) -> str | None:
        if not self.contract_id:
            return None

        try:
            source_account = self.server.load_account(self.keypair.public_key)

            content_hash_bytes = bytes.fromhex(content_hash)
            embedding_hash_bytes = bytes.fromhex(embedding_hash)

            tx_builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100_000,
            )

            tx_builder.append_invoke_contract_function_op(
                contract_id=self.contract_id,
                function_name="register_knowledge",
                parameters=[
                    scval.to_address(owner_public_key),
                    scval.to_bytes(content_hash_bytes),
                    scval.to_bytes(embedding_hash_bytes),
                    scval.to_string(manifest_cid),
                    scval.to_string(source_url or ""),
                ],
            )

            tx = tx_builder.set_timeout(300).build()

            simulate_resp = self.server.simulate_transaction(tx)
            if simulate_resp.error:
                raise Exception(f"Simulation failed: {simulate_resp.error}")

            tx = self.server.prepare_transaction(tx, simulate_resp)
            tx.sign(self.keypair)

            send_resp = self.server.send_transaction(tx)

            tx_hash = send_resp.hash
            status = send_resp.status

            if status == "ERROR":
                raise Exception("Transaction submission failed")

            for _ in range(30):
                time.sleep(1)
                get_resp = self.server.get_transaction(tx_hash)
                if get_resp.status == GetTransactionStatus.SUCCESS:
                    return tx_hash
                elif get_resp.status == GetTransactionStatus.FAILED:
                    raise Exception("Transaction failed on-chain")

            return tx_hash

        except Exception as e:
            print(f"Blockchain registration failed: {e}")
            return None

    async def verify_record(self, content_hash: str) -> dict | None:
        if not self.contract_id:
            return None

        try:
            source_account = self.server.load_account(self.keypair.public_key)
            content_hash_bytes = bytes.fromhex(content_hash)

            tx_builder = TransactionBuilder(
                source_account=source_account,
                network_passphrase=self.network_passphrase,
                base_fee=100_000,
            )

            tx_builder.append_invoke_contract_function_op(
                contract_id=self.contract_id,
                function_name="get_record",
                parameters=[
                    scval.to_bytes(content_hash_bytes),
                ],
            )

            tx = tx_builder.set_timeout(300).build()
            simulate_resp = self.server.simulate_transaction(tx)

            if simulate_resp.results:
                return {"verified": True, "content_hash": content_hash}
            return None

        except Exception:
            return None


blockchain_service = BlockchainService()
