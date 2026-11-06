"""Multi-variant paired screen: every seating is played once with B and once with each variant.

Same pairing as scripts/ab_test.py (same build_seatings seeds), but B is shared across variants
and the h2h cell is skipped.  usage: screen.py OUT SNGS SEED FIELDS SCHEDULES B VAR=json ...
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, '.')
sys.path.insert(0, 'scripts')
from ab_test import AB_FIELDS, paired  # noqa: E402
from benchmark import PAYOUTS, SCHEDULES, rebundle  # noqa: E402
from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402

SCR = os.path.dirname(os.path.abspath(__file__))


def main():
    out, sngs, seed, fields, scheds, bspec = sys.argv[1:7]
    sngs, seed = int(sngs), int(seed)
    base = json.load(open(bspec.split(':', 1)[1]))
    eb = parse_entry(bspec)
    eb['label'] = 'B'
    variants = []
    for arg in sys.argv[7:]:
        name, delta = arg.split('=', 1)
        p = dict(base)
        p.update(json.loads(delta))
        path = os.path.join(SCR, 'v_' + name + '.json')
        json.dump(p, open(path, 'w'))
        e = parse_entry('prep:' + path)
        e['label'] = name
        variants.append(e)
    payouts = PAYOUTS['default']
    fair = sum(payouts) / len(payouts)
    pool = make_pool(rebundle('bundles/nlhe_rng.nlb', payouts), None, 3)
    res = {v['label']: [] for v in variants}
    t0 = time.time()
    fh = open(out, 'a')
    try:
        for sname in scheds.split(','):
            kw = {'payouts': list(payouts), 'hands_per_level': SCHEDULES[sname]}
            for fname in fields.split(','):
                field = [parse_entry(k, w) for k, w in AB_FIELDS[fname].items()]
                seats0 = build_seatings(field, sngs, seed, fixed=[{'label': 'slot'}])
                games = []
                for seats, sd in seats0:
                    for e in [eb] + variants:
                        games.append(([e if s.get('label') == 'slot' else s for s in seats], sd))
                rows = run_games(games, sng_kw=kw, pool=pool, raw=True)
                for v in variants:
                    m, se, n = paired(rows, v['label'], 'B')
                    res[v['label']].append((sname, fname, 100 * m / fair, 100 * se / fair))
                    print(f"{v['label']:<10}{sname:<8}{fname:<20}{100 * m / fair:+7.2f}% ±{100 * se / fair:.2f}",
                          file=fh, flush=True)
                print(f'# done {sname} {fname} [{time.time() - t0:.0f}s]', file=fh, flush=True)
    finally:
        pool.terminate()
    print('\n# SUMMARY (mean of cells, % of fair; worst cell = lowest t)', file=fh)
    for name, cells in res.items():
        k = len(cells)
        mean = sum(c[2] for c in cells) / k
        se = math.sqrt(sum(c[3] ** 2 for c in cells)) / k
        worst = min(cells, key=lambda c: c[2] / max(c[3], 1e-9))
        print(f'{name:<10} mean {mean:+.2f} ± {se:.2f}   worst {worst[0]}/{worst[1]} {worst[2]:+.2f} ± {worst[3]:.2f}'
              f' (t={worst[2] / max(worst[3], 1e-9):+.1f})', file=fh, flush=True)
    fh.close()


if __name__ == '__main__':
    main()
