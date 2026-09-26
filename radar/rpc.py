"""Minimal client for Solana's public RPC endpoint. No API key needed - just a
throttle and a retry loop, because the public endpoint is shared and rate
limited. Every other module in this project talks to the chain through this
one class, so there is exactly one place that knows how to be a polite
citizen of a free, shared resource."""
from __future__ import annotations
import time
import requests


class SolanaRPC:
    def __init__(self, url: str = "https://api.mainnet-beta.solana.com", min_interval_ms: int = 400):
        self.url = url
        self.min_interval = min_interval_ms / 1000.0
        self._last = 0.0

    def _throttle(self):
        dt = time.time() - self._last
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self._last = time.time()

    def _call(self, method: str, params: list, retries: int = 4):
        last_err = None
        for attempt in range(retries):
            self._throttle()
            try:
                r = requests.post(self.url, json={"jsonrpc": "2.0", "id": 1,
                                                    "method": method, "params": params},
                                   timeout=20)
                if r.status_code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                d = r.json()
                if "error" in d:
                    last_err = d["error"]
                    time.sleep(1 * (attempt + 1))
                    continue
                return d.get("result")
            except requests.RequestException as e:
                last_err = e
                time.sleep(1 * (attempt + 1))
        raise RuntimeError(f"RPC {method} failed after {retries} attempts: {last_err}")

    def get_account_info(self, address: str, encoding: str = "base64"):
        return self._call("getAccountInfo", [address, {"encoding": encoding}])

    def get_token_largest_accounts(self, mint: str):
        return self._call("getTokenLargestAccounts", [mint])

    def get_signatures_for_address(self, address: str, before: str | None = None, limit: int = 1000):
        params = {"limit": limit}
        if before:
            params["before"] = before
        return self._call("getSignaturesForAddress", [address, params])

    def get_transaction(self, signature: str):
        # maxSupportedTransactionVersion=1: Solana now has versioned transactions
        # beyond legacy/0, and a client that only accepts 0 silently fails on a
        # meaningful slice of real traffic (we lost ~2500 transactions to this
        # exact mistake before catching it - see the README for that story).
        return self._call("getTransaction", [signature,
                           {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 1}])
