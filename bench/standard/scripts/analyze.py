"""Compute standard poker stats for our bot from measure.py logs.

usage: python analyze.py rr.jsonl [gh.jsonl ...]
"""
import itertools
import json
import sys
from collections import defaultdict

sys.path.insert(0, "/Users/revanthguda/poker")
from nolimit.runtime import CALL, FOLD, POST, RAISE, load_tables  # noqa: E402

T = load_tables(path="/Users/revanthguda/poker/bundles/nlhe_rng.nlb")
EV = T.ev
D = T.v.D


def eq_random(hole, board):
    """Share of random opponent holdings our river hand beats (ties half)."""
    used = set(hole) | set(board)
    mine = EV.best(tuple(hole), tuple(board))
    w = n = 0
    for c in itertools.combinations([c for c in range(D) if c not in used], 2):
        v = EV.best(c, tuple(board))
        w += 1.0 if mine > v else 0.5 if mine == v else 0.0
        n += 1
    return w / n


def positions(order):
    n = len(order)
    lab = {}
    if n == 2:
        return {order[0]: "SB(HU)", order[1]: "BB(HU)"}
    lab[order[-1]] = "BB"
    lab[order[-2]] = "SB"
    names = ["BTN", "CO", "HJ", "LJ", "MP", "UTG"]
    for i, s in enumerate(reversed(order[:-2])):
        lab[s] = names[i] if i < len(names) else "UTG"
    return lab


def action_order(r):
    n = len(r["stacks"])
    hist = r["hist"]
    posts = [h[0] for h in hist if h[2] == POST]
    dealt = {h[0] for h in hist}
    dealt.update(i for i in range(n) if r["in_hand"][i])
    bb_seat = posts[1] if len(posts) >= 2 else (posts[0] if posts else r["button"])
    return [s for s in ((bb_seat + k) % n for k in range(1, n + 1)) if s in dealt]


def band(bb):
    if bb > 60:
        return "60+bb"
    if bb > 30:
        return "30-60bb"
    if bb > 20:
        return "20-30bb"
    if bb > 12:
        return "12-20bb"
    return "<=12bb"


BANDS = ["60+bb", "30-60bb", "20-30bb", "12-20bb", "<=12bb"]
POS = ["UTG", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB", "SB(HU)", "BB(HU)"]


class C:
    """counter of opportunities / successes"""

    def __init__(self):
        self.d = defaultdict(lambda: [0, 0])

    def add(self, key, hit, w=1):
        x = self.d[key]
        x[0] += w
        x[1] += 1 if hit else 0

    def get(self, key):
        n, h = self.d.get(key, (0, 0))
        return (100.0 * h / n if n else float("nan")), n


def hands_of(sng):
    cur = []
    for r in sng["log"]:
        if "end" in r:
            yield cur, r
            cur = []
        else:
            cur.append(r)


def analyze(paths):
    S = defaultdict(C)
    vals = defaultdict(list)
    n_sng = 0
    for path in paths:
        for line in open(path):
            sng = json.loads(line)
            n_sng += 1
            for dec, end in hands_of(sng):
                if not dec:
                    continue          # walk / not dealt a decision
                me = dec[0]["seat"]
                pre = [r for r in dec if r["street"] == 0]
                if not pre:
                    continue
                r0 = pre[0]
                order = action_order(r0)
                labs = positions(order)
                pos = labs.get(me, "?")
                n_dealt = len(order)
                opps = [s for s in range(len(r0["stacks"])) if r0["in_hand"][s] and s != me]
                my_tot = r0["stacks"][me] + r0["bets"][me]
                eff = min(my_tot, max(r0["stacks"][s] + r0["bets"][s] for s in opps)) / r0["bb"]
                bd = band(eff)
                hist0 = [h for h in r0["hist"] if h[1] == 0]
                raises = [h for h in hist0 if h[2] == RAISE]
                limps = [h for h in hist0 if h[2] == CALL and h[3] > 0]
                bb = r0["bb"]
                a0 = r0["act"]
                jam0 = a0 == RAISE and r0["amt"] >= r0["max_to"]
                vpip = any(r["act"] in (CALL, RAISE) and r["to_call"] > 0 or r["act"] == RAISE for r in pre)
                pfr = any(r["act"] == RAISE for r in pre)
                full = "full" if n_dealt >= 6 else ("short" if n_dealt >= 3 else "HU")
                S["vpip"].add((full, bd), vpip)
                S["pfr"].add((full, bd), pfr)
                S["vpip_all"].add("all", vpip)
                S["pfr_all"].add("all", pfr)
                # first-in (unopened, not BB)
                if not raises and not limps and r0["to_call"] > 0:
                    S["rfi"].add((pos, bd), a0 == RAISE)
                    S["rfi_jam"].add((pos, bd), jam0)
                    S["rfi_limp"].add((pos, bd), a0 == CALL)
                    S["rfi_n"].add((full, pos, bd), a0 == RAISE)
                    if a0 == RAISE and not jam0:
                        vals[("open_size", bd)].append(r0["amt"] / bb)
                    if a0 == RAISE and not jam0 and bd != "<=12bb":
                        S["rfi_raise_nonjam"].add(bd, True)
                    if a0 == RAISE:
                        vals[("open_pct_max", pos, bd)].append(r0["pct"])
                    # facing 3-bet after our open
                    if a0 == RAISE and not jam0:
                        later = [r for r in pre[1:] if r["to_call"] > 0]
                        if later:
                            r1 = later[0]
                            jam_faced = any(h[2] == RAISE and h[4] for h in r1["hist"][len(r0["hist"]):] if h[1] == 0)
                            key = "vs3b_jam" if jam_faced else "vs3b"
                            S[key + "_fold"].add(bd, r1["act"] == FOLD)
                            S[key + "_4b"].add(bd, r1["act"] == RAISE)
                # limped pot as BB
                if pos in ("BB", "BB(HU)") and not raises and r0["to_call"] == 0:
                    S["bb_vs_limp_raise"].add(bd, a0 == RAISE)
                # vs one open (non all-in), no callers in between
                if len(raises) == 1 and not raises[0][4]:
                    callers = [h for h in hist0 if h[2] == CALL and hist0.index(h) > hist0.index(raises[0])]
                    osz = raises[0][3] / bb
                    if not callers:
                        S["vs_open_3b"].add((pos, bd), a0 == RAISE)
                        S["vs_open_call"].add((pos, bd), a0 == CALL)
                        S["vs_open_def"].add((pos, bd), a0 != FOLD)
                        S["vs_open_3b_all"].add(bd if pos not in ("BB", "BB(HU)") else "BB " + bd, a0 == RAISE)
                        if pos in ("BB", "BB(HU)"):
                            sz = "min(<=2.1x)" if osz <= 2.1 else ("2.1-2.6x" if osz <= 2.6 else ("2.6-3.5x" if osz <= 3.5 else ">3.5x"))
                            S["bb_def"].add((sz, bd), a0 != FOLD)
                            S["bb_3b"].add((sz, bd), a0 == RAISE)
                            S["bb_def_sz"].add(sz, a0 != FOLD)
                        if a0 == RAISE:
                            vals[("3b_jam", bd)].append(1 if r0["amt"] >= r0["max_to"] else 0)
                            vals[("3b_size_x", bd)].append(r0["amt"] / raises[0][3])
                # vs one all-in shove, no callers
                if len(raises) == 1 and raises[0][4]:
                    callers = [h for h in hist0 if h[2] == CALL and hist0.index(h) > hist0.index(raises[0])]
                    if not callers:
                        shover = raises[0][0]
                        spos = labs.get(shover, "?")
                        k = ("HU" if n_dealt == 2 else ("BBvsSB" if pos == "BB" and spos == "SB" else pos), band(eff))
                        S["call_shove"].add(k, a0 != FOLD)
                        S["call_shove_all"].add(band(eff), a0 != FOLD)
                # SB first in vs BB only (blind vs blind)
                if pos in ("SB", "SB(HU)") and not raises and not limps:
                    S["sb_raise"].add((pos, bd), a0 == RAISE and not jam0)
                    S["sb_jam"].add((pos, bd), jam0)
                    S["sb_limp"].add((pos, bd), a0 == CALL)
                    S["sb_fold"].add((pos, bd), a0 == FOLD)

                # ---- postflop ----
                fr = [h for h in end["hist"] if h[1] == 0 and h[2] == RAISE]
                pfr_seat = fr[-1][0] if fr else None
                # use the full hand history (end record) for street facts
                fh = end["hist"]
                post = [r for r in dec if r["street"] > 0]
                if not post:
                    continue
                for st in (1, 2, 3):
                    rs = [r for r in post if r["street"] == st]
                    if not rs:
                        continue
                    r = rs[0]
                    n_in = sum(r["in_hand"])
                    stname = ("flop", "turn", "river")[st - 1]
                    hu = "HU" if n_in == 2 else "MW"
                    bets_before = [h for h in r["hist"] if h[1] == st and h[2] == RAISE]
                    pot_start = r["pot"] - sum(r["bets"])
                    # c-bet
                    if st == 1 and pfr_seat == me and not bets_before:
                        nn = len(r["stacks"])
                        live = [x for x in ((r["button"] + k) % nn for k in range(1, nn + 1)) if r["in_hand"][x]]
                        ip = "IP" if live[-1] == me else "OOP"
                        S["cbet"].add((hu, n_in), r["act"] == RAISE)
                        S["cbet_ip"].add((hu, ip), r["act"] == RAISE)
                        S["cbet_hu_mw"].add(hu, r["act"] == RAISE)
                        if r["act"] == RAISE:
                            vals[("cbet_size", hu)].append((r["amt"] - r["bets"][me]) / max(pot_start, 1))
                    # donk / probe: not pfr, first bet
                    if st == 1 and pfr_seat is not None and pfr_seat != me and not bets_before and r["in_hand"][pfr_seat]:
                        # we act before pfr this street?
                        S["donk_or_stab"].add(hu, r["act"] == RAISE)
                    # facing c-bet
                    if st == 1 and pfr_seat is not None and pfr_seat != me and len(bets_before) == 1 \
                            and bets_before[0][0] == pfr_seat and r["to_call"] > 0:
                        frac = r["to_call"] / max(r["pot"] - r["to_call"], 1)  # bet / pot before it (approx)
                        bet = bets_before[0][3]
                        frac = bet / max(pot_start, 1)
                        S["fold_cbet"].add(hu, r["act"] == FOLD)
                        S["raise_cbet"].add(hu, r["act"] == RAISE)
                        sz = "<=40%" if frac <= 0.4 else ("40-75%" if frac <= 0.75 else (">75%"))
                        S["fold_cbet_sz"].add((hu, sz), r["act"] == FOLD)
                    # facing a single bet HU, any street: fold vs size (MDF)
                    if n_in == 2 and len(bets_before) == 1 and r["to_call"] > 0:
                        bet = bets_before[0][3]
                        frac = bet / max(pot_start, 1)
                        if bets_before[0][4]:
                            szb = "allin"
                        else:
                            szb = "<=40%" if frac <= 0.4 else ("40-60%" if frac <= 0.6 else ("60-85%" if frac <= 0.85 else ("85-120%" if frac <= 1.2 else ">120%")))
                        S["fold_vs_bet"].add((stname, szb), r["act"] == FOLD)
                        S["fold_vs_bet_st"].add(stname, r["act"] == FOLD)
                        S["raise_vs_bet"].add(stname, r["act"] == RAISE)
                        vals[("fvb_frac", stname, szb)].append(frac)
                    # checked to us / first to act, betting freq
                    if not bets_before:
                        S["bet_when_unbet"].add((stname, hu), r["act"] == RAISE)
                        if r["act"] == RAISE:
                            frac = (r["amt"] - r["bets"][me]) / max(pot_start, 1)
                            allin = r["amt"] >= r["max_to"]
                            vals[("bet_size", stname)].append(frac)
                            vals[("bet_allin", stname)].append(1 if allin else 0)
                            if st == 3 and n_in == 2:
                                eqr = eq_random(r["hole"], r["board"])
                                vals[("river_bet_eq", "all")].append((frac, eqr, allin))
                    # check-raise
                    if r["act"] == CALL and r["to_call"] == 0:
                        later = [x for x in rs[1:] if x["to_call"] > 0]
                        if later:
                            S["check_raise"].add((stname, hu), later[0]["act"] == RAISE)
                # showdown / river outcomes
                sd = end["showdown"]
                if str(me) in sd:
                    S["wtsd"].add("all", True)
                    board = end["board"]
                    mine = EV.best(tuple(sd[str(me)]), tuple(board))
                    best_other = max(EV.best(tuple(v), tuple(board)) for k, v in sd.items() if k != str(me))
                    won = mine >= best_other
                    S["wsd"].add("all", won)
                    # did we bet/raise the river and get called?
                    rv = [x for x in post if x["street"] == 3 and x["act"] == RAISE]
                    if rv:
                        S["river_bet_called_won"].add("all", won)
                else:
                    S["wtsd"].add("all", False)
                S["saw_flop"].add("all", True)
    return S, vals, n_sng


def fmt(x):
    p, n = x
    return f"{p:5.1f}% (n={n})" if n else "  -  "


def report(S, vals, n_sng, title):
    import statistics as st
    out = [f"## {title}  ({n_sng} SNGs)", ""]
    out.append(f"VPIP {fmt(S['vpip_all'].get('all'))}  PFR {fmt(S['pfr_all'].get('all'))}")
    out.append("")
    out.append("VPIP/PFR by table size and stack band:")
    for full in ("full", "short", "HU"):
        row = [f"  {full:5}"]
        for bd in BANDS:
            v, p = S["vpip"].get((full, bd)), S["pfr"].get((full, bd))
            if v[1]:
                row.append(f"{bd}: {v[0]:.0f}/{p[0]:.0f} (n={v[1]})")
        out.append("  ".join(row))
    out.append("")
    out.append("RFI raise% (incl jam) [jam%] [limp%] by position x band:")
    for pos in POS:
        row = [f"  {pos:7}"]
        for bd in BANDS:
            r = S["rfi"].get((pos, bd))
            if r[1] >= 10:
                j = S["rfi_jam"].get((pos, bd))[0]
                l = S["rfi_limp"].get((pos, bd))[0]
                row.append(f"{bd}: {r[0]:4.0f} [j{j:.0f} l{l:.0f}] n={r[1]}")
        if len(row) > 1:
            out.append("  ".join(row))
    out.append("")
    out.append("RFI raise% 6-8 handed only (compare to full-ring charts):")
    for pos in POS[:7]:
        row = [f"  {pos:7}"]
        for bd in BANDS[:3]:
            r = S["rfi_n"].get(("full", pos, bd))
            if r[1] >= 10:
                row.append(f"{bd}: {r[0]:4.0f} n={r[1]}")
        if len(row) > 1:
            out.append("  ".join(row))
    out.append("")
    for bd in BANDS:
        v = vals.get(("open_size", bd))
        if v:
            out.append(f"open size (non-jam) {bd}: median {st.median(v):.2f}bb mean {st.mean(v):.2f} n={len(v)}")
    out.append("")
    out.append("vs single open (no callers): 3bet% / call% / defend% by position x band:")
    for pos in POS:
        row = [f"  {pos:7}"]
        for bd in BANDS:
            r = S["vs_open_3b"].get((pos, bd))
            if r[1] >= 10:
                c = S["vs_open_call"].get((pos, bd))[0]
                row.append(f"{bd}: {r[0]:.0f}/{c:.0f}/{r[0]+c:.0f} n={r[1]}")
        if len(row) > 1:
            out.append("  ".join(row))
    for bd in BANDS:
        v = vals.get(("3b_jam", bd))
        if v:
            sz = vals.get(("3b_size_x", bd))
            out.append(f"  3bets {bd}: jam share {100*sum(v)/len(v):.0f}%, median size {st.median(sz):.1f}x open, n={len(v)}")
    out.append("")
    out.append("BB defend% / 3bet% vs open size (no callers):")
    for k in sorted(S["bb_def"].d):
        d, b = S["bb_def"].get(k), S["bb_3b"].get(k)
        if d[1] >= 10:
            out.append(f"  {k}: defend {d[0]:.0f}% 3bet {b[0]:.0f}% n={d[1]}")
    out.append("")
    out.append("Facing 3bet after our open: fold% / 4bet%:")
    for key in ("vs3b", "vs3b_jam"):
        for bd in BANDS:
            f = S[key + "_fold"].get(bd)
            if f[1] >= 5:
                out.append(f"  {key} {bd}: fold {f[0]:.0f}% 4bet/jam {S[key + '_4b'].get(bd)[0]:.0f}% n={f[1]}")
    out.append("")
    out.append("BB vs limp: raise% " + "  ".join(f"{bd}: {fmt(S['bb_vs_limp_raise'].get(bd))}" for bd in BANDS))
    out.append("")
    out.append("SB first-in (folded to SB): raise / jam / limp / fold:")
    for pos in ("SB", "SB(HU)"):
        for bd in BANDS:
            r = S["sb_raise"].get((pos, bd))
            if r[1] >= 10:
                out.append(f"  {pos} {bd}: raise {r[0]:.0f} jam {S['sb_jam'].get((pos, bd))[0]:.0f} "
                           f"limp {S['sb_limp'].get((pos, bd))[0]:.0f} fold {S['sb_fold'].get((pos, bd))[0]:.0f} n={r[1]}")
    out.append("")
    out.append("Call% vs a single all-in (no callers):")
    for k in sorted(S["call_shove"].d):
        r = S["call_shove"].get(k)
        if r[1] >= 10:
            out.append(f"  {k}: {r[0]:.0f}% n={r[1]}")
    out.append("")
    out.append("Postflop:")
    for k in sorted(S["cbet_ip"].d):
        out.append(f"    c-bet {k}: {fmt(S['cbet_ip'].get(k))}")
    out.append("  flop c-bet HU " + fmt(S["cbet_hu_mw"].get("HU")) + "  MW " + fmt(S["cbet_hu_mw"].get("MW")))
    for k in sorted(S["cbet"].d):
        out.append(f"    c-bet with {k[1]} players: {fmt(S['cbet'].get(k))}")
    for hu in ("HU", "MW"):
        v = vals.get(("cbet_size", hu))
        if v:
            out.append(f"  c-bet size {hu}: median {st.median(v):.2f} pot, mean {st.mean(v):.2f}, "
                       f"<=40%: {100*sum(1 for x in v if x <= 0.4)/len(v):.0f}%  >=90%: {100*sum(1 for x in v if x >= 0.9)/len(v):.0f}%")
    out.append("  fold to c-bet HU " + fmt(S["fold_cbet"].get("HU")) + "  MW " + fmt(S["fold_cbet"].get("MW"))
               + "   raise c-bet HU " + fmt(S["raise_cbet"].get("HU")))
    for k in sorted(S["fold_cbet_sz"].d):
        out.append(f"    fold to c-bet {k}: {fmt(S['fold_cbet_sz'].get(k))}")
    out.append("  donk/lead into PFR (flop): HU " + fmt(S["donk_or_stab"].get("HU")) + " MW " + fmt(S["donk_or_stab"].get("MW")))
    out.append("  HU fold vs single bet by street x size (MDF = 1-b/(1+b) of pot frac b):")
    for k in sorted(S["fold_vs_bet"].d):
        r = S["fold_vs_bet"].get(k)
        fr = vals.get(("fvb_frac",) + k)
        b = st.mean(fr) if fr else 0
        mdf_fold = 100 * b / (1 + 2 * b) if k[1] != "allin" else float("nan")   # alpha = b/(1+2b)? see note
        alpha = 100 * b / (1 + b)
        if r[1] >= 10:
            out.append(f"    {k}: fold {r[0]:.0f}% n={r[1]}  (mean bet {b:.2f} pot; MDF-implied max fold {alpha:.0f}%)")
    for stname in ("flop", "turn", "river"):
        out.append(f"  {stname}: fold vs bet HU {fmt(S['fold_vs_bet_st'].get(stname))}  raise {fmt(S['raise_vs_bet'].get(stname))}"
                   f"  bet when unbet HU {fmt(S['bet_when_unbet'].get((stname, 'HU')))} MW {fmt(S['bet_when_unbet'].get((stname, 'MW')))}"
                   f"  check-raise HU {fmt(S['check_raise'].get((stname, 'HU')))}")
        v = vals.get(("bet_size", stname))
        if v:
            a = vals[("bet_allin", stname)]
            out.append(f"     bet size median {st.median(v):.2f} pot; all-in share {100*sum(a)/len(a):.0f}%; "
                       f"buckets <=0.4:{100*sum(1 for x in v if x<=0.4)/len(v):.0f}% 0.4-0.8:{100*sum(1 for x in v if 0.4<x<=0.8)/len(v):.0f}% "
                       f"0.8-1.2:{100*sum(1 for x in v if 0.8<x<=1.2)/len(v):.0f}% >1.2:{100*sum(1 for x in v if x>1.2)/len(v):.0f}%")
    rb = vals.get(("river_bet_eq", "all"), [])
    if rb:
        nonai = [x for x in rb if not x[2]]
        for name, sub in (("all", rb), ("non-allin", nonai)):
            if not sub:
                continue
            air = sum(1 for _f, e, _a in sub if e < 0.5)
            weak = sum(1 for _f, e, _a in sub if e < 0.65)
            out.append(f"  HU river bets ({name}, n={len(sub)}): share with eq-vs-random <50% (air) {100*air/len(sub):.0f}%, <65% {100*weak/len(sub):.0f}%")
    out.append("  WTSD (of flops seen) " + fmt(S["wtsd"].get("all")) + "  W$SD " + fmt(S["wsd"].get("all"))
               + "  won when our river bet/raise reached SD " + fmt(S["river_bet_called_won"].get("all")))
    return "\n".join(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        S, vals, n = analyze([path])
        print(report(S, vals, n, path))
        print()
