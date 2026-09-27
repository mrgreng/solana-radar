# Superteam Earn / Colosseum Crypto World's Fair — Submission Draft

## Project name
Solana Radar

## One-liner (X/Twitter-length)
Real on-chain safety checks and smart-money confluence detection for Solana
memecoins — no API key, no indexer, just the public RPC and balance-delta math.

## Track to submit to (primary)
**"Build something live on Solana data" — Solami — 3,000 USDG**
Direct match: the whole project is live on-chain data read straight from
public RPC (SPL mint/freeze layout decoding, LP holder lookups, balance-delta
swap reconstruction) with zero third-party API dependency.

*Secondary:* the FAQ says the same project can be submitted to multiple
side-tracks. Worth also checking 1-2 regional Superteam tracks (Germany,
Netherlands, etc.) for eligibility — I can't confirm residency/regional
requirements for you, that's a quick check on your end.

## Links
- GitHub: https://github.com/mrgreng/solana-radar
- Demo video: https://share.descript.com/view/QzK9wzFQCna
- Live demo / hosted instance: *(optional — CLI-only for now, see Description)*

## Description (long form)

**Problem.** Two failure modes dominate the Solana memecoin trading tool
space: (1) "rug checker" tools relying on shallow heuristics rather than
reading the actual mint/freeze authority and LP holder state, and (2)
"copy the top trader" tools that trust a leaderboard's *displayed* PnL
instead of the wallet's real on-chain history.

**What we found before writing a line of this project's code.** While doing
private trading research, we mapped a social-trading platform's #3-ranked
trader by 30-day PnL to their real wallet via public identity resolution.
Full on-chain history: a net loss of $6,334. The #2-ranked trader on the
same board: a net loss of $35,275. Nobody had checked, because checking
means reconstructing every trade from raw balance deltas instead of trusting
a UI. Across the trades we *did* verify this way, tokens independently
bought by two or more separately-tracked wallets showed a 54% hit rate and
positive median return, against 39% and a negative median for tokens only
one wallet touched — a real, measured effect, not a guess.

**What we built.** Solana Radar packages the general-purpose engine behind
that research as open infrastructure:

1. `radar/safety.py` — decodes the SPL Token mint account directly to check
   mint authority and freeze authority renouncement, and checks an LP mint's
   largest holder against known burn addresses / trusted lockers. Fails
   closed: no proof of safety, no pass.
2. `radar/swaps.py` + `radar/confluence.py` — detects real swaps by reading
   balance deltas (not parsing any specific DEX's instructions), which also
   solves "received vs. bought" for free (an airdrop is one balance leg, a
   real swap is always two). This lets us find *every* buyer of a token
   without already knowing who they are, by checking which transaction
   signers had a clean two-leg swap.

**Validated live**, not just against test fixtures: `app.py check` on USDC's
mint correctly returns *unsafe* (Circle genuinely holds active mint/freeze
authority — expected for a regulated stablecoin, exactly what we'd want
flagged for an anonymous launch); on BONK's mint it correctly returns *safe*
(both authorities renounced on-chain).

**Tech stack.** Pure Python, `requests` for RPC calls, no framework, no paid
service, no API key. 14 unit tests against mocked RPC responses (`pytest`).

**What's next.** A real sell-simulation honeypot check once we can pin a
stable aggregator API; a live confluence feed instead of on-demand checks;
a broader LP-locker whitelist.

## Team
*(mrgreng)*

## Ask
Submitting for the Solami track prize and evaluation; open to feedback from
judges on extending the LP-locker whitelist and the live-feed roadmap item.
