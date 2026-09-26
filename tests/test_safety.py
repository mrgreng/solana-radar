"""Unit tests for radar.safety - mocked RPC responses, no live network calls."""
from __future__ import annotations
import base64, struct
from unittest.mock import MagicMock

from radar import safety


def _mint_account_b64(mint_authority_present: bool, freeze_authority_present: bool) -> str:
    raw = bytearray(82)
    struct.pack_into("<I", raw, 0, 1 if mint_authority_present else 0)
    struct.pack_into("<I", raw, 46, 1 if freeze_authority_present else 0)
    return base64.b64encode(bytes(raw)).decode()


def _fake_rpc(get_account_info_return):
    rpc = MagicMock()
    rpc.get_account_info.return_value = get_account_info_return
    return rpc


def test_both_authorities_renounced_is_safe():
    rpc = _fake_rpc({"value": {"data": [_mint_account_b64(False, False)]}})
    ok, reasons = safety.check_mint_and_freeze_authority(rpc, "FakeMint111")
    assert ok and reasons == []


def test_mint_authority_present_is_unsafe():
    rpc = _fake_rpc({"value": {"data": [_mint_account_b64(True, False)]}})
    ok, reasons = safety.check_mint_and_freeze_authority(rpc, "FakeMint111")
    assert not ok and "mint authority" in reasons[0]


def test_freeze_authority_present_is_unsafe():
    rpc = _fake_rpc({"value": {"data": [_mint_account_b64(False, True)]}})
    ok, reasons = safety.check_mint_and_freeze_authority(rpc, "FakeMint111")
    assert not ok and "freeze authority" in reasons[0]


def test_mint_not_found_fails_closed():
    rpc = _fake_rpc({"value": None})
    ok, reasons = safety.check_mint_and_freeze_authority(rpc, "Nonexistent")
    assert not ok


def test_lp_burned_passes():
    rpc = MagicMock()
    rpc.get_token_largest_accounts.return_value = {"value": [{"address": "LpAcct1", "amount": "1000"}]}
    rpc.get_account_info.return_value = {
        "value": {"data": {"parsed": {"info": {"owner": next(iter(safety.KNOWN_BURN_ADDRESSES))}}}}}
    ok, reasons = safety.check_lp_locked_or_burned(rpc, "FakeLpMint")
    assert ok and reasons == []


def test_lp_held_by_unknown_owner_fails_closed():
    rpc = MagicMock()
    rpc.get_token_largest_accounts.return_value = {"value": [{"address": "LpAcct1", "amount": "1000"}]}
    rpc.get_account_info.return_value = {"value": {"data": {"parsed": {"info": {"owner": "SomeDevWallet"}}}}}
    ok, reasons = safety.check_lp_locked_or_burned(rpc, "FakeLpMint")
    assert not ok


def test_no_lp_holders_fails_closed():
    rpc = MagicMock()
    rpc.get_token_largest_accounts.return_value = {"value": []}
    ok, reasons = safety.check_lp_locked_or_burned(rpc, "FakeLpMint")
    assert not ok


def test_looks_like_solana_pubkey():
    assert safety.looks_like_solana_pubkey("5FGoPPj1nL8LCnfVnpTmreqQtqLuMXXAwuS1uahMrp8V")
    assert not safety.looks_like_solana_pubkey("0xa0670863BD5CD0D60022BaB2eed78E81e1A06bcE")
    assert not safety.looks_like_solana_pubkey("")


def test_safety_report_rejects_bad_address():
    rpc = MagicMock()
    report = safety.safety_report(rpc, "not-an-address")
    assert report["safe"] is False
