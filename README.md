# Solana Radar

Two real, working, on-chain tools for Solana memecoin traders, built on nothing
but the public RPC endpoint - no API key, no paid indexer, no third-party
service that can change its terms on you.

1. **Safety check** - is this token's mint authority renounced? Is the freeze
   authority gone? Is the liquidity actually locked or burned? Answered by
   reading the SPL Token account layout and the LP mint's holder list
   directly, in one call each.
2. **Smart-money confluence** - who has been buying this token, and are any
   of *your* trusted wallets already in it? Answered by reading balance
   deltas on the token's own transaction history - no need to already know
   who the buyers are.

## Why this is harder than it sounds (and why it matters)

Most "is this a rug" tools rely on a handful of heuristics scraped from a
block explorer's API, and most "copy the whales" tools trust a leaderboard's
own displayed numbers. Both of those failure modes are real, and we hit both
of them while building the private trading research this project grew out of:

- We mapped a social-trading platform's #3-ranked trader (by 30-day PnL,
  displayed in the tens of millions) to their on-chain wallet via public
  identity-resolution tools. Full on-chain history, no truncation: **a net
  loss of $6,334.** The #2-ranked trader on the same leaderboard: a net loss
  of **$35,275.** The leaderboard numbers and the on-chain reality were not
  in the same universe. Nobody had checked, because checking requires
  reconstructing every trade from raw balance deltas instead of trusting a
  UI.
- Across hundreds of thousands of real trades we did verify this way, tokens
  bought by two or more independently-tracked wallets showed a **54% hit
  rate and positive median return**, against **39% and a negative median**
  for tokens only one wallet touched. That's the empirical basis for the
  confluence check in this repo - it isn't a guess, it's a measured effect.

Both tools here are the general-purpose engine behind that research, stripped
of the private wallet list and trading strategy, released as standalone
infrastructure anyone can point at their own watchlist.

## How the safety check works

Solana SPL tokens store mint authority and freeze authority directly in the
mint account, in a fixed binary layout. We decode it ourselves:

```
mint_authority_option != 0   -> the dev can still mint unlimited new supply
freeze_authority_option != 0 -> the dev can still freeze any holder's tokens
```

For liquidity, we read the LP mint's largest holder: if it isn't a known burn
address or an explicitly trusted locker program, the liquidity can be pulled
in one transaction by whoever controls it. No proof of lock/burn is treated
as **unsafe** - this fails closed, always.

*Honest limitation:* this does not simulate a sell through an aggregator
(a stricter honeypot test some tools attempt). We left it out rather than
ship it against a third-party API contract we couldn't verify was stable.
Mint authority + freeze authority + LP lock catch the large majority of real
Solana rug patterns without that dependency.

*Live-network sanity check* (run yourself with `app.py check`): USDC's mint
correctly comes back `unsafe` - Circle genuinely holds an active mint and
freeze authority over it, which is expected and disclosed for a regulated
stablecoin, but is exactly the pattern this tool exists to flag for an
anonymous memecoin launch. BONK's mint correctly comes back `safe` - both
authorities are renounced on-chain. The heuristic is aimed at new/anonymous
launches, not at evaluating centralized, disclosed stablecoins.

## How the confluence check works

A genuine swap always has two balance legs in the same transaction -
something goes down, something goes up. An airdrop or gift is a single leg.
This is how we tell "bought" from "received" without parsing any DEX's
instruction format, and it's also how we find buyers we didn't already know
about: scan a token mint's own recent signatures, check every *signer*
touched by each transaction's balance changes (a pool never signs; a buyer
always does), and you get every clean buy on that token - no indexer needed.

## Try it

```bash
pip install -r requirements.txt

# Is this token's mint/freeze authority renounced? Is the LP locked?
python app.py check <TOKEN_MINT> --lp <LP_MINT>

# Who's been buying it, and is anyone on my watchlist already in?
python app.py watch <TOKEN_MINT> --wallets examples/demo_watchlist.txt
```

Run the test suite (mocked RPC, no network calls, no key needed):

```bash
pytest tests/ -v
```

## What's next

- A real sell-simulation honeypot check, once we can pin a stable
  aggregator API contract to build it against.
- A live confluence *feed* (watch new tokens as they get bought by 2+
  watchlisted wallets, instead of checking one token on demand).
- Extending the LP-locker whitelist beyond the single burn address we ship
  with (Streamflow and other locker programs, added as we verify their
  account layouts).

Built for the Colosseum Crypto World's Fair hackathon, on top of research
first developed for a private paper-trading fund.
