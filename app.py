#!/usr/bin/env python3
"""Solana Radar - CLI demo.

  python app.py check <TOKEN_MINT> [--lp <LP_MINT>]
      Real on-chain safety check: mint authority, freeze authority, LP lock.

  python app.py watch <TOKEN_MINT> --wallets <FILE_OR_COMMA_LIST>
      Who has been buying this token recently, and is anyone on your
      watchlist already in it?

No API key required - everything runs against Solana's public RPC.
"""
from __future__ import annotations
import argparse, json, sys

from radar.rpc import SolanaRPC
from radar.safety import safety_report
from radar.confluence import check_watchlist, scan_recent_buyers


def _load_wallets(spec: str) -> list[str]:
    if spec.endswith(".txt") or spec.endswith(".csv"):
        with open(spec) as f:
            return [line.strip() for line in f if line.strip()]
    return [w.strip() for w in spec.split(",") if w.strip()]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_check = sub.add_parser("check", help="on-chain safety check for a token")
    p_check.add_argument("mint")
    p_check.add_argument("--lp", default=None, help="LP mint address, if you have it")

    p_watch = sub.add_parser("watch", help="who's buying this token, and is my watchlist in it")
    p_watch.add_argument("mint")
    p_watch.add_argument("--wallets", default=None, help="comma-separated addresses, or a .txt/.csv file")
    p_watch.add_argument("--max-pages", type=int, default=10)
    p_watch.add_argument("--max-tx", type=int, default=200)

    args = ap.parse_args()
    rpc = SolanaRPC()

    if args.cmd == "check":
        report = safety_report(rpc, args.mint, args.lp)
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["safe"] else 1)

    if args.cmd == "watch":
        if args.wallets:
            wallets = _load_wallets(args.wallets)
            result = check_watchlist(rpc, args.mint, wallets, max_pages=args.max_pages, max_tx_fetched=args.max_tx)
            print(f"scanned {result['tx_fetched']} transactions across {result['pages_scanned']} pages"
                  f"{' (truncated - very active token)' if result['truncated'] else ''}")
            print(f"distinct buyers found: {len(result['buyers'])}")
            print(f"watchlist hits: {len(result['watchlist_hits'])}")
            for w, info in result["watchlist_hits"].items():
                print(f"  {w} bought at {info['block_time']} ({info['quote_amount']:.3f} {info['quote_symbol']})")
            if result["confluence"]:
                print("\n>> CONFLUENCE: 2+ watchlisted wallets are independently in this token.")
        else:
            result = scan_recent_buyers(rpc, args.mint, max_pages=args.max_pages, max_tx_fetched=args.max_tx)
            print(f"scanned {result['tx_fetched']} transactions across {result['pages_scanned']} pages"
                  f"{' (truncated - very active token)' if result['truncated'] else ''}")
            print(f"distinct buyers found: {len(result['buyers'])}")


if __name__ == "__main__":
    main()
