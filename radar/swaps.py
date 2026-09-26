"""Extract real swaps from a Solana transaction by reading balance DELTAS
(preTokenBalances/postTokenBalances + native SOL), instead of parsing each
DEX's own instruction format. This works with any DEX, known or not, because
it never looks at the instruction - only at what actually moved.

This also solves "received vs. bought" for free: an airdrop is a single
balance delta (the token goes up, nothing else moves in the same
transaction). A real swap always has two legs - something goes down,
something goes up, in the same transaction. One leg only -> not a swap,
discarded.
"""
from __future__ import annotations

NATIVE_SOL = "So11111111111111111111111111111111111111112"


def extract_swap(tx: dict, wallet: str, quote_mints: dict):
    """Swap detection for a KNOWN wallet (you already know whose balance to read)."""
    if not tx:
        return None
    meta = tx.get("meta")
    if not meta or meta.get("err") is not None:
        return None

    pre = {b["mint"]: b for b in (meta.get("preTokenBalances") or []) if b.get("owner") == wallet}
    post = {b["mint"]: b for b in (meta.get("postTokenBalances") or []) if b.get("owner") == wallet}

    deltas: dict[str, float] = {}
    for mint in set(pre) | set(post):
        pre_amt = float((pre[mint]["uiTokenAmount"].get("uiAmount") or 0)) if mint in pre else 0.0
        post_amt = float((post[mint]["uiTokenAmount"].get("uiAmount") or 0)) if mint in post else 0.0
        d = post_amt - pre_amt
        if abs(d) > 1e-12:
            deltas[mint] = d

    keys = tx["transaction"]["message"]["accountKeys"]
    idx = None
    for i, k in enumerate(keys):
        pk = k.get("pubkey") if isinstance(k, dict) else k
        if pk == wallet:
            idx = i
            break
    if idx is not None and idx < len(meta.get("preBalances", [])):
        pre_sol = meta["preBalances"][idx] / 1e9
        post_sol = meta["postBalances"][idx] / 1e9
        sol_delta = post_sol - pre_sol
        if idx == 0:
            sol_delta += meta.get("fee", 0) / 1e9
        if abs(sol_delta) > 1e-6:
            deltas[NATIVE_SOL] = deltas.get(NATIVE_SOL, 0.0) + sol_delta

    if len(deltas) < 2:
        return None  # pure transfer (received or sent), not a swap

    quote_leg, token_legs = None, []
    for mint, d in deltas.items():
        if mint in quote_mints:
            if quote_leg is not None:
                return None  # two "quote" legs -> ambiguous, skip
            quote_leg = (mint, d)
        else:
            token_legs.append((mint, d))

    if quote_leg is None or len(token_legs) != 1:
        return None  # token<->token or multi-token swap: out of scope for v1

    qmint, qdelta = quote_leg
    tmint, tdelta = token_legs[0]
    if qdelta < 0 < tdelta:
        side, quote_amount, token_amount = "buy", -qdelta, tdelta
    elif qdelta > 0 > tdelta:
        side, quote_amount, token_amount = "sell", qdelta, -tdelta
    else:
        return None

    if token_amount <= 0:
        return None

    return {
        "side": side, "quote_symbol": quote_mints[qmint]["symbol"], "quote_amount": quote_amount,
        "token_mint": tmint, "token_amount": token_amount, "price": quote_amount / token_amount,
        "block_time": tx.get("blockTime"),
    }


def extract_buyers(tx: dict, token_mint: str, quote_mints: dict) -> list[dict]:
    """Swap detection with NO known wallet up front: scan every owner touched by
    the transaction's balance changes (typically 2-4: the buyer, the pool, a
    service ATA) and return every clean purchase of the given mint. Used for
    reverse discovery - given a token, who else bought it early? - without
    needing to already know the buyer's address.

    Only owners that SIGNED the transaction are considered: a pool/vault never
    signs (the user signs to authorize spending their own funds), so this
    discards the pool's own balance delta without needing to know that DEX's
    program ID."""
    if not tx:
        return []
    meta = tx.get("meta")
    if not meta or meta.get("err") is not None:
        return []
    keys = tx["transaction"]["message"]["accountKeys"]
    signers = {k["pubkey"] for k in keys if isinstance(k, dict) and k.get("signer")}
    owners = {b["owner"] for b in (meta.get("preTokenBalances") or []) + (meta.get("postTokenBalances") or [])
              if b.get("owner")}
    candidates = (owners & signers) if signers else owners
    out = []
    for owner in candidates:
        swap = extract_swap(tx, owner, quote_mints)
        if swap and swap["side"] == "buy" and swap["token_mint"] == token_mint:
            swap["wallet"] = owner
            out.append(swap)
    return out
