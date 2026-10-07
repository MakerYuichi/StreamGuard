"""
Generates a small synthetic edge-stream CSV so you can test the
baseline script immediately, without waiting on the real DARPA
dataset. Swap this file out later -- just point baseline_batch.py
at the real DARPA CSV instead (same column names).
"""

import random
import csv
import time

OUTPUT_FILE = "fake_traffic.csv"
NORMAL_ROWS = 500
BURST_ROWS = 40  # a sudden burst of one repeated edge = the "attack"

start_time = int(time.time()) - 600  # pretend this happened 10 min ago

rows = []

# Normal background traffic: random src/dst pairs, spread over time
for i in range(NORMAL_ROWS):
    rows.append({
        "src": f"192.168.1.{random.randint(1, 50)}",
        "dst": f"10.0.0.{random.randint(1, 50)}",
        "timestamp": start_time + random.randint(0, 550),
        "label": 0,
    })

# Injected "attack": one src hammering one dst repeatedly in a short window
attacker = "192.168.1.666"
victim = "10.0.0.99"
burst_start = start_time + 560
for i in range(BURST_ROWS):
    rows.append({
        "src": attacker,
        "dst": victim,
        "timestamp": burst_start + random.randint(0, 5),  # all within 5 seconds
        "label": 1,
    })

rows.sort(key=lambda r: r["timestamp"])

with open(OUTPUT_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["src", "dst", "timestamp", "label"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")
print(f"Injected attack: {attacker} -> {victim}, {BURST_ROWS} rows around t={burst_start}")