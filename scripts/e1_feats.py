"""Richer features for the spec's postflop equity vs one random hand (e1), FALLBACK_SPEC2 §2b."""
from fallback import spec_bot as S


def e1_feats(hole, board):
    """(hi, lo, fb, cb, pb, top, mine, over, fd_nut, fb4, sb4): all in about -1..1 or 0/1.
    mine = the rank that makes my hand (paired hole rank, pocket pair, or high card), scaled;
    over = board cards above `mine` (0..2 scaled /2); fd_nut = I hold the ace of a 3+/4-card
    flush suit; fb4 = 4+ board cards of one suit; sb4 = the board alone has 4 ranks within a span of 5."""
    h = [S.card(c) for c in hole]
    b = [S.card(c) for c in board]
    hr = sorted((r for r, _ in h), reverse=True)
    br = [r for r, _ in b]
    hi, lo, fb, cb, pb = S.board_feats(hole, board)
    top = (max(br) - 8) / 6.0
    paired = [r for r in hr if r in br]
    mine = paired[0] if paired else (hr[0] if hr[0] == hr[1] else hr[0])
    over = min(sum(1 for r in set(br) if r > mine), 2) / 2.0
    sc = {}
    for _, s in b:
        sc[s] = sc.get(s, 0) + 1
    fd_nut = 0.0
    for s, n in sc.items():
        if n >= 2 and any(r == 14 and ss == s for r, ss in h):
            fd_nut = 1.0
    fb4 = float(max(sc.values()) >= 4)
    u = sorted(set(br + ([1] if 14 in br else [])))
    sb4 = float(any(u[i + 3] - u[i] <= 4 for i in range(len(u) - 3)))
    return (hi, lo, fb, cb, pb, top, (mine - 8) / 6.0, over, fd_nut, fb4, sb4)
