"""
IPFS service using Pinata Cloud for decentralized storage.
Free tier: 1GB storage, no local daemon required.

Sign up: https://app.pinata.cloud/register
"""

import json
import hashlib
import httpx
from app.core.config import get_settings

settings = get_settings()


class IPFSService:
    def __init__(self):
        self.pinata_api_url = "https://api.pinata.cloud"
        self.pinata_gateway = "https://gateway.pinata.cloud/ipfs"
        self._available: bool | None = None

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {settings.pinata_jwt}",
        }

    async def _check_availability(self) -> bool:
        if self._available is not None:
            return self._available

        if not settings.pinata_jwt:
            print("[IPFSService] No Pinata JWT configured, using mock mode")
            self._available = False
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.pinata_api_url}/data/testAuthentication",
                    headers=self._headers,
                )
                self._available = resp.status_code == 200
                if self._available:
                    print("[IPFSService] Connected to Pinata Cloud")
                else:
                    print(f"[IPFSService] Pinata auth failed: {resp.status_code}")
        except Exception as e:
            print(f"[IPFSService] Pinata unavailable: {e}")
            self._available = False

        return self._available

    async def upload_json(self, data: dict) -> str:
        if not await self._check_availability():
            return self._mock_cid(data)

        json_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.pinata_api_url}/pinning/pinFileToIPFS",
                headers=self._headers,
                files={"file": ("manifest.json", json_bytes, "application/json")},
                data={
                    "pinataMetadata": json.dumps({
                        "name": data.get("title", "manifest.json"),
                    }),
                    "pinataOptions": json.dumps({"cidVersion": 1}),
                },
            )
            resp.raise_for_status()
            result = resp.json()
            cid = result["IpfsHash"]
            print(f"[IPFSService] Pinned to IPFS: {cid}")
            return cid

    async def upload_text(self, content: str, filename: str = "content.txt") -> str:
        if not await self._check_availability():
            return self._mock_cid({"content": content[:100]})

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.pinata_api_url}/pinning/pinFileToIPFS",
                headers=self._headers,
                files={"file": (filename, content.encode("utf-8"), "text/plain")},
                data={
                    "pinataMetadata": json.dumps({"name": filename}),
                    "pinataOptions": json.dumps({"cidVersion": 1}),
                },
            )
            resp.raise_for_status()
            return resp.json()["IpfsHash"]

    async def get_content(self, cid: str) -> bytes:
        if not await self._check_availability():
            return b'{"mock": true}'

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.pinata_gateway}/{cid}")
            resp.raise_for_status()
            return resp.content

    def _mock_cid(self, data: dict) -> str:
        content = json.dumps(data).encode()
        h = hashlib.sha256(content).hexdigest()[:46]
        return f"Qm{h}"


ipfs_service = IPFSService()
