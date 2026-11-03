"""Hand-category frequencies for a variant, to sanity-check the ranking order on the day.

    python scripts/variant_stats.py --variant shortdeck
    python scripts/variant_stats.py --variant variants/day.json

If the announcement doesn't say how categories rank, "rarer beats more common" is the
usual convention; compare the printed order against the frequencies.
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nolimit.runtime import CATEGORY_NAMES, HIGH, PRESETS, Evaluator, Variant  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="nlhe")
    ap.add_argument("--samples", type=int, default=50_000)
    args = ap.parse_args()
    if args.variant in PRESETS:
        v = PRESETS[args.variant]
    else:
        with open(args.variant) as fh:
            v = Variant.from_dict(json.load(fh))
    ev = Evaluator(v)
    rng = random.Random(0)
    five = [0] * len(CATEGORY_NAMES)
    show = [0] * len(CATEGORY_NAMES)
    for _ in range(args.samples):
        five[ev.category(ev.eval5(rng.sample(range(v.D), 5)))] += 1
        cards = rng.sample(range(v.D), v.n_hole + v.n_board)
        show[ev.category(ev.best(cards[:v.n_hole], cards[v.n_hole:]))] += 1
    print(f"{v.name}: deck {v.D}, {v.n_hole} hole, board {v.streets}, hole_used={v.hole_used}")
    print(f"{'category':<16}{'5-card freq':>13}{'best at showdown':>18}   rank here (0 = weakest)")
    for cat in sorted(range(len(CATEGORY_NAMES)), key=lambda c: v.category_order.index(c)):
        print(f"{CATEGORY_NAMES[cat]:<16}{100 * five[cat] / args.samples:>12.3f}%"
              f"{100 * show[cat] / args.samples:>17.3f}%   {v.category_order.index(cat)}")
    # High card stays at the bottom by convention, even in decks where pairs are commoner.
    rarity = [HIGH] + sorted((c for c in range(len(CATEGORY_NAMES)) if c != HIGH), key=lambda c: -five[c])
    if [c for c in rarity if five[c]] != [c for c in v.category_order if five[c]]:
        print("\nnote: this order is NOT 'rarer 5-card hand beats commoner'. By rarity it would be:")
        print("  " + " < ".join(CATEGORY_NAMES[c] for c in rarity if five[c]))


if __name__ == "__main__":
    main()
