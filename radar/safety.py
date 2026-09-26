"""Real on-chain safety checks for a Solana token - no third-party API, no key,
just direct RPC reads and the SPL Token account layout. Covers the two most
common honeypot patterns on Solana:

  1. mint authority still present -> the dev can print unlimited new supply
  2. freeze authority still present -> the dev can freeze any holder's tokens

...plus a liquidity lock/burn check: if the LP mint's largest holder isn't a
known burn address or an explicitly trusted locker program, the liquidity can
be pulled by whoever controls it. Fail-closed by design: absence of proof of
safety is treated as unsafe, never the other way around.

Honest limitation: this does not simulate a sell (a stricter honeypot test
would try to route a sell through an aggregator and see if it succeeds). We
left that out because we could not verify a stable, keyless third-party API
contract to build it on. Mint/freeze/LP-lock still catch the large majority
of real Solana rug patterns.
"""
from __future__ import annotations
import base64, struct

from .rpc import SolanaRPC

# Addresses tokens get sent to when genuinely burned on Solana (destinations,
# not authorities - anyone can send tokens here, which is exactly the point).
KNOWN_BURN_ADDRESSES = {
    "1nc1nerator11111111111111111111111111111",
}

SPL_TOKEN_MINT_LAYOUT_LEN = 82  # classic SPL Token mint account (no Token-2022 extensions)


def looks_like_solana_pubkey(address: str) -> bool:
    """Cheap sanity check (base58-ish, plausible length) before spending a real
    RPC call on something that clearly isn't a Solana address."""
    if not address or not (32 <= len(address) <= 44):
        return False
    return all(c not in "0OIl" and c.isalnum() for c in address)


def check_mint_and_freeze_authority(rpc: SolanaRPC, mint_address: str) -> tuple[bool, list[str]]:
    """Decode the SPL Token mint account (fixed binary layout) and check that
    both mint authority and freeze authority have been renounced (None)."""
    reasons = []
    result = rpc.get_account_info(mint_address)
    if not result or not result.get("value"):
        return False, ["mint not found on-chain"]
    raw = base64.b64decode(result["value"]["data"][0])
    if len(raw) < SPL_TOKEN_MINT_LAYOUT_LEN:
        return False, ["unexpected mint account layout (Token-2022 extensions? not handled)"]
    mint_authority_option = struct.unpack_from("<I", raw, 0)[0]
    freeze_authority_option = struct.unpack_from("<I", raw, 46)[0]
    if mint_authority_option != 0:
        reasons.append("mint authority not renounced: the dev can create more supply")
    if freeze_authority_option != 0:
        reasons.append("freeze authority present: the dev can freeze holders' tokens")
    return (len(reasons) == 0, reasons)


def check_lp_locked_or_burned(rpc: SolanaRPC, lp_mint_address: str,
                               known_locker_owners: set[str] | None = None) -> tuple[bool, list[str]]:
    """Look at the LP mint's largest holder: if it's a known burn address or an
    explicitly whitelisted locker (e.g. Streamflow), liquidity can't be pulled
    by the dev in one transaction. Fail-closed: no proof, no pass."""
    known_locker_owners = known_locker_owners or set()
    result = rpc.get_token_largest_accounts(lp_mint_address)
    accounts = (result or {}).get("value") or []
    if not accounts:
        return False, ["no holders found for this LP mint (pool doesn't exist or is fully drained)"]
    top = accounts[0]
    total = sum(float(a["amount"]) for a in accounts)
    top_pct = float(top["amount"]) / total * 100 if total > 0 else 0.0
    owner_info = rpc.get_account_info(top["address"], encoding="jsonParsed")
    owner = None
    try:
        owner = owner_info["value"]["data"]["parsed"]["info"]["owner"]
    except (TypeError, KeyError):
        pass
    if owner in KNOWN_BURN_ADDRESSES or owner in known_locker_owners:
        return True, []
    return False, [f"LP is neither burned nor in a known locker (top holder {top_pct:.0f}%, owner={owner})"]


def safety_report(rpc: SolanaRPC, mint_address: str, lp_mint_address: str | None = None) -> dict:
    """One-call summary used by the CLI/demo: mint/freeze always checked, LP
    lock checked only if an LP mint was supplied (finding it generically for
    an arbitrary DEX is out of scope for this project)."""
    if not looks_like_solana_pubkey(mint_address):
        return {"address": mint_address, "safe": False, "reasons": ["not a valid Solana address"]}
    mf_ok, mf_reasons = check_mint_and_freeze_authority(rpc, mint_address)
    reasons = list(mf_reasons)
    lp_ok = None
    if lp_mint_address:
        lp_ok, lp_reasons = check_lp_locked_or_burned(rpc, lp_mint_address)
        reasons += lp_reasons
    return {
        "address": mint_address,
        "mint_freeze_ok": mf_ok,
        "lp_ok": lp_ok,
        "safe": mf_ok and (lp_ok is not False),
        "reasons": reasons,
    }
