"""Unit tests for radar.swaps - synthetic transactions, no live network calls."""
from __future__ import annotations
from radar.swaps import extract_swap, extract_buyers, NATIVE_SOL

QUOTE_MINTS = {NATIVE_SOL: {"symbol": "SOL", "decimals": 9}}
TOKEN = "TargetToken1111111111111111111111111111111"


def _bal(owner, mint, amount):
    return {"owner": owner, "mint": mint, "uiTokenAmount": {"uiAmount": amount}}


def _tx(pre, post, pre_sol, post_sol, keys, signers=None, fee=5000, err=None):
    signers = signers if signers is not None else {keys[0]}
    return {
        "blockTime": 1700000000,
        "meta": {"err": err, "fee": fee, "preTokenBalances": pre, "postTokenBalances": post,
                  "preBalances": pre_sol, "postBalances": post_sol},
        "transaction": {"message": {"accountKeys": [{"pubkey": k, "signer": k in signers} for k in keys]}},
    }


def test_extract_swap_detects_a_clean_buy():
    tx = _tx(
        pre=[_bal("buyer", TOKEN, 0)], post=[_bal("buyer", TOKEN, 50)],
        pre_sol=[2_000_000_000], post_sol=[1_000_000_000], keys=["buyer"],
    )
    swap = extract_swap(tx, "buyer", QUOTE_MINTS)
    assert swap["side"] == "buy" and swap["token_mint"] == TOKEN


def test_extract_swap_ignores_pure_transfer():
    tx = _tx(pre=[_bal("someone", TOKEN, 0)], post=[_bal("someone", TOKEN, 50)],
              pre_sol=[0], post_sol=[0], keys=["someone"])
    assert extract_swap(tx, "someone", QUOTE_MINTS) is None


def test_extract_swap_failed_tx_returns_none():
    tx = _tx(pre=[], post=[], pre_sol=[0], post_sol=[0], keys=["x"], err={"InstructionError": []})
    assert extract_swap(tx, "x", QUOTE_MINTS) is None


def test_extract_buyers_finds_the_buyer_not_the_pool():
    tx = _tx(
        pre=[_bal("buyer1", TOKEN, 0), _bal("pool", TOKEN, 1000)],
        post=[_bal("buyer1", TOKEN, 50), _bal("pool", TOKEN, 950)],
        pre_sol=[2_000_000_000, 500_000_000], post_sol=[1_000_000_000, 1_500_000_000],
        keys=["buyer1", "pool"],
    )
    out = extract_buyers(tx, TOKEN, QUOTE_MINTS)
    assert len(out) == 1 and out[0]["wallet"] == "buyer1"


def test_extract_buyers_ignores_sells_and_other_tokens():
    other = "OtherToken22222222222222222222222222222222"
    tx = _tx(
        pre=[_bal("seller", TOKEN, 100), _bal("pool", TOKEN, 900)],
        post=[_bal("seller", TOKEN, 0), _bal("pool", TOKEN, 1000)],
        pre_sol=[1_000_000_000, 2_000_000_000], post_sol=[2_000_000_000, 1_000_000_000],
        keys=["seller", "pool"],
    )
    assert extract_buyers(tx, TOKEN, QUOTE_MINTS) == []
    assert extract_buyers(tx, other, QUOTE_MINTS) == []
