"""List tokens that just traded on pump.fun, read straight from the blockchain.

No website needed: this asks for the pump.fun program's most recent
transactions and decodes which tokens they traded.

Usage (from the repo root): python scripts/find_tokens.py [transactions to scan, default 40]
"""

import sys

from dotenv import load_dotenv

sys.path.insert(0, ".")
from meme_hawkes.fetch import PUMP_PROGRAM, events_in_transaction, rpc, rpc_url  # noqa: E402

load_dotenv()
n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
url = rpc_url()

seen = {}
for s in rpc(url, "getSignaturesForAddress", [PUMP_PROGRAM, {"limit": n}]):
    if s["err"] is not None:
        continue
    tx = rpc(url, "getTransaction", [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 1}])
    if tx is None:
        continue
    for event in events_in_transaction(tx):
        seen[event["mint"]] = seen.get(event["mint"], 0) + 1

if not seen:
    sys.exit("No trades decoded from recent pump.fun transactions: tell Claude.")
print(f"Tokens traded in the last {n} pump.fun transactions:")
for mint, count in sorted(seen.items(), key=lambda kv: -kv[1]):
    print(f"  {mint}   ({count} trades seen)")
