"""Chart every recorded price for a match, from the opening quote weeks before
kickoff to the last in-play tick.

Usage:
    FIVEDOLLARFOOTBALL_API_KEY=fb_live_... python odds_movement.py
    FIVEDOLLARFOOTBALL_API_KEY=fb_live_... python odds_movement.py --fixture 3197771745
    FIVEDOLLARFOOTBALL_API_KEY=fb_live_... python odds_movement.py --bookmaker pinnacle

Odds history needs the Ultra plan; Free and Pro keys get a 403 insufficient_plan.
"""

import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")  # write a file; no display needed
import matplotlib.pyplot as plt
from fivedollarfootball import APIError, Client


def latest_finished(client, search, country):
    """The most recent finished match of the first league matching the search."""
    leagues = client.leagues(search=search, country=country)
    league = next((l for l in leagues if l.get("has_standings")), None)
    if league is None:
        sys.exit(f'No league matches "{search}" in {country}.')
    fixtures = client.league_fixtures(league["id"], status="finished", per_page=1)
    if not fixtures:
        sys.exit(f'{league["name"]} has no finished match on your plan.')
    return fixtures[0]


def main():
    parser = argparse.ArgumentParser(description="Chart a match's 1X2 odds movement.")
    parser.add_argument("--fixture", type=int, help="fixture id (default: latest finished match of --league)")
    parser.add_argument("--league", default="Premier League", help='league to pick the latest match from')
    parser.add_argument("--country", default="GB-ENG", help="country code as listed by /v1/countries")
    parser.add_argument("--bookmaker", default="bet365", help="bookmaker slug, see /v1/bookmakers")
    parser.add_argument("--out", default="movement.png", help="output file")
    args = parser.parse_args()

    key = os.environ.get("FIVEDOLLARFOOTBALL_API_KEY")
    if not key:
        sys.exit("Set FIVEDOLLARFOOTBALL_API_KEY. Odds history needs an Ultra key: https://5dollarfootballapi.com/pricing")

    client = Client(key)
    try:
        # 1. The match: the one asked for, or the league's most recent finished one.
        match = client.fixture(args.fixture) if args.fixture else latest_finished(client, args.league, args.country)
        name = f'{match["teams"]["home"]["name"]} v {match["teams"]["away"]["name"]}'

        # 2. Every recorded 1X2 price, oldest first, across all pages.
        history = client.iter_all(
            client.odds_history, fixture_id=match["id"], market="1x2",
            bookmaker=args.bookmaker, per_page=500,
        )
        # A tick without a price marks a moment the book was not quoting.
        ticks = [t for t in history if t["home"]]
    except APIError as err:
        sys.exit(f"API error {err.status_code} {err.code}: {err.message}")

    if not ticks:
        sys.exit(f"{name}: {args.bookmaker} has no 1X2 history for this match.")

    kickoff = next((i for i, t in enumerate(ticks) if t["minute"] is not None), len(ticks))

    # 3. One step line per outcome. A log scale keeps the in-play swings readable.
    for side in ("home", "draw", "away"):
        plt.step(range(len(ticks)), [t[side] for t in ticks], where="post", label=side)
    plt.axvline(kickoff, linestyle="--", color="grey")
    plt.yscale("log")
    plt.title(f"{name}, {args.bookmaker} 1X2")
    plt.xlabel("tick (dashed line = kickoff)")
    plt.ylabel("decimal odds")
    plt.legend()
    plt.savefig(args.out, dpi=150)

    print(f"{name}: {len(ticks)} ticks, {kickoff} pre-match, {len(ticks) - kickoff} in-play -> {args.out}")


if __name__ == "__main__":
    main()
