"""Smart-money confluence: given a token, who has been buying it, and are any
of them on a watchlist of wallets you already trust?

The core idea, proven out on a much larger private dataset before this
public build: wallets that independently buy the same token early are a
real, measurable signal. Two of our verified wallets sharing a token in
common has empirically shown a higher hit-rate and a positive median return,
against a negative median for tokens only one wallet touched (see README).

Technique: page a token mint's own signature history backwards, extract every
clean buy via balance-delta detection (swaps.extract_buyers - no need to
already know who's buying), and check the buyer set against an optional
watchlist. No paid API, no indexer - just the public RPC.
"""
from __future__ import annotations
import time
from collections import defaultdict

from .rpc import SolanaRPC
from .swaps import extract_buyers

DEFAULT_QUOTE_MINTS = {
    "So11111111111111111111111111111111111111112": {"symbol": "SOL", "decimals": 9},
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {"symbol": "USDC", "decimals": 6},
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": {"symbol": "USDT", "decimals": 6},
}


def scan_recent_buyers(rpc: SolanaRPC, token_mint: str, quote_mints: dict | None = None,
                        max_pages: int = 10, max_tx_fetched: int = 200) -> dict:
    """Scans the token mint's most recent signatures (from the chain tip
    backwards) and returns every distinct buyer found in that window, with
    their most recent buy. Bounded on two axes (pages of signatures listed,
    transactions actually fetched) because a viral token can have thousands
    of buyers in a single hour - past the cap we stop and say so honestly,
    we don't pretend to have seen everything."""
    quote_mints = quote_mints or DEFAULT_QUOTE_MINTS
    found: dict[str, dict] = {}
    before, pages, tx_fetched, truncated = None, 0, 0, False
    while pages < max_pages and tx_fetched < max_tx_fetched:
        batch = rpc.get_signatures_for_address(token_mint, before=before, limit=1000)
        pages += 1
        if not batch:
            break
        for sig_info in batch:
            if sig_info.get("err") is not None:
                continue
            if tx_fetched >= max_tx_fetched:
                truncated = True
                break
            tx = rpc.get_transaction(sig_info["signature"])
            tx_fetched += 1
            for swap in extract_buyers(tx, token_mint, quote_mints):
                w = swap["wallet"]
                if w not in found or swap["block_time"] > found[w]["block_time"]:
                    found[w] = swap
        before = batch[-1]["signature"]
        if truncated:
            break
    return {"buyers": found, "pages_scanned": pages, "tx_fetched": tx_fetched, "truncated": truncated}


def check_watchlist(rpc: SolanaRPC, token_mint: str, watchlist: list[str],
                     quote_mints: dict | None = None, **scan_kwargs) -> dict:
    """Same scan, plus a direct answer to 'are any of MY trusted wallets in
    this token, and when did they buy?'."""
    result = scan_recent_buyers(rpc, token_mint, quote_mints, **scan_kwargs)
    watchlist_set = set(watchlist)
    hits = {w: info for w, info in result["buyers"].items() if w in watchlist_set}
    result["watchlist_hits"] = hits
    result["confluence"] = len(hits) >= 2  # 2+ trusted wallets independently in the same token
    return result
