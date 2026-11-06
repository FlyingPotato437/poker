import json, sys
sys.path.insert(0, "/Users/revanthguda/poker")
from nolimit.runtime import RAISE, FOLD, CALL, POST
from collections import Counter
c=Counter()
for i,line in enumerate(open(sys.argv[1])):
    sng=json.loads(line); me=sng["me"]
    for r in sng["log"]:
        if "end" not in r: continue
        h=r["hist"]; posts=[x for x in h if x[2]==POST]
        seats={x[0] for x in h}
        if len(posts)!=2 or len(seats)!=2: continue
        sb=posts[0][0]
        if sb==me: continue
        bb=posts[1][1] if False else posts[1][3]
        first=[x for x in h if x[1]==0 and x[2]!=POST and x[0]==sb]
        if not first: continue
        a=first[0]
        c["n"]+=1
        c["jam" if a[2]==RAISE and a[4] else ("raise" if a[2]==RAISE else ("limp" if a[2]==CALL else "fold"))]+=1
print({k:(v if k=="n" else round(100*v/c["n"],1)) for k,v in c.items()})
