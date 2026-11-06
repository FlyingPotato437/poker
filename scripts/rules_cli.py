"""Command-line flags for the engine's optional house rules (nolimit/engine.py), shared by
run_tournament.py, ab_test.py and stipulation_sweep.py. Every flag is off by default."""


def add_rule_args(ap):
    g = ap.add_argument_group("house rules (all off by default)")
    g.add_argument("--ante-bb", type=float, default=0.0, help="ante from everyone, as a fraction of the BB")
    g.add_argument("--bb-ante", type=float, default=0.0, help="big-blind ante in BB (1 = standard BB ante)")
    g.add_argument("--straddle", action="store_true", help="UTG posts a 2 BB straddle every hand")
    g.add_argument("--bomb-every", type=int, default=0, help="bomb pot every N hands")
    g.add_argument("--bomb-bb", type=float, default=2.0, help="each player's bomb-pot post in BB")
    g.add_argument("--run-twice", action="store_true", help="all-in pots are run twice")
    g.add_argument("--bounty-72", type=float, default=0.0, help="7-2 offsuit bounty in BB from each player")
    g.add_argument("--bounty-72-noshow", action="store_true", help="the 7-2 bounty pays without showdown too")
    g.add_argument("--ko-points", type=float, default=0.0, help="points per knockout to the buster")
    g.add_argument("--max-bet-bb", type=float, default=0.0, help="cap on a bet/raise increment, in BB")
    g.add_argument("--max-raises", type=int, default=0, help="most bets/raises per betting round")
    g.add_argument("--dead-button", action="store_true", help="dead-button rule when players bust")
    g.add_argument("--cap-scoring", choices=("icm", "chips"), default="icm", help="survivor scoring at the cap")
    g.add_argument("--stack-spread", type=float, default=0.0, help="uneven starting stacks, +-fraction")


def rule_kwargs(args):
    """Only the rules that are switched on, so default runs pass the engine nothing new."""
    kw = {}
    for k in ("ante_bb", "bb_ante", "straddle", "run_twice", "bounty_72", "bounty_72_noshow", "ko_points",
              "max_bet_bb", "max_raises", "dead_button", "stack_spread"):
        if getattr(args, k, None):
            kw[k] = getattr(args, k)
    if getattr(args, "bomb_every", 0):
        kw["bomb_every"], kw["bomb_bb"] = args.bomb_every, args.bomb_bb
    if getattr(args, "cap_scoring", "icm") != "icm":
        kw["cap_scoring"] = args.cap_scoring
    return kw
