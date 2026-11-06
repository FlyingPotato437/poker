import json, sys
sys.path.insert(0, "/Users/revanthguda/poker")
from nolimit.runtime import SeatStats, ingest_history, RAISE, FOLD, POST
import statistics as st
ys=[]; calls=[]; pcts=[]; shove_freq=[]
for i,line in enumerate(open(sys.argv[1])):
    if i>=200: break
    sng=json.loads(line); stats=[SeatStats() for _ in range(8)]
    # opponent HU SB shove frequency (empirical) in HU phase
    for r in sng["log"]:
        if "end" in r:
            h=r["hist"]
            # HU hands: 2 posts and the SB acts first; check villain SB action
            ingest_history(stats, h); continue
        if r["street"]!=0: continue
        n_dealt=len({x[0] for x in r["hist"]} | {k for k in range(8) if r["in_hand"][k]})
        if n_dealt!=2: continue
        raises=[x for x in r["hist"] if x[1]==0 and x[2]==RAISE]
        if len(raises)==1 and raises[0][4] and r["to_call"]>0:
            sh=raises[0][0]; s=stats[sh]
            y=max(s.rate("shove"), s.rate("pfr")*0.8)*1.5
            eff=min(r["stacks"][r["seat"]]+r["bets"][r["seat"]], r["stacks"][sh]+r["bets"][sh])/r["bb"]
            if eff<=15:
                ys.append(min(y,1)); calls.append(r["act"]!=FOLD); pcts.append(r["pct"])
print("n",len(ys),"median assumed shove range y",round(st.median(ys),3),"mean",round(st.mean(ys),3),"call%",round(100*sum(calls)/len(calls),1))
