"""Process or report on synthetic local data; no external notification."""
import argparse
import json
import os
from pathlib import Path
from backend.api import init, claim, finish, metrics, connect

def report(path):
    with connect(path) as db:
        return {
            **metrics(path),
            "by_campaign":[dict(r) for r in db.execute("SELECT campaign,COUNT(*) AS leads,SUM(status='Convertido') AS converted FROM leads GROUP BY campaign ORDER BY campaign")],
            "by_month_utc":[dict(r) for r in db.execute("SELECT strftime('%Y-%m',created,'unixepoch') AS month,COUNT(*) AS leads FROM leads GROUP BY month ORDER BY month")],
            "mode":"synthetic local; no messages sent"
        }

def process(path, success=True, limit=20):
    results=[]
    for _ in range(limit):
        event=claim(path)
        if not event:
            break
        accepted=finish(path,event["id"],event["lease"],success)
        results.append({"id":event["id"],"acknowledged":accepted,"simulated_success":success})
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["process","fail","report"])
    parser.add_argument("--limit",type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=100:
        parser.error("limit must be between 1 and 100")
    path=Path(os.environ.get("ESSENZA_DB","essenza-demo.sqlite3"))
    init(path)
    result=report(path) if args.command=="report" else process(path,args.command=="process",args.limit)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
