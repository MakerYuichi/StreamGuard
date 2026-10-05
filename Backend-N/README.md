# StreamGuard — Phase 1 (Role 3: Backend / Storage Infrastructure)

This folder gets you from zero to a **proven, working Kafka → Consumer pipe**,
with Postgres and Redis verified and ready for Phase 2.

Nothing here does real anomaly scoring yet — that's intentional. Phase 1's
only job is to prove every pipe works, using fake/placeholder data, so
Phase 2 is just "swap the placeholder for the real thing" instead of
debugging infrastructure and algorithm logic at the same time.

---

## Prerequisites

- Docker + Docker Compose installed
- Python 3.9+
- (Optional but recommended) a virtual environment

---

## Step-by-step

### 1. Start the infrastructure

```bash
docker compose up -d
docker compose ps
```

Wait until all three services (`streamguard-redpanda`, `streamguard-postgres`,
`streamguard-redis`) show as healthy/running. This can take 15-30 seconds on
first startup (Postgres is running the init SQL script automatically).

If something looks stuck:
```bash
docker compose logs -f
```

### 2. Install Python dependencies

```bash
cd consumer
pip install -r requirements.txt
```

### 3. Verify Postgres + Redis actually work

```bash
python db_check.py
```

Expected output ends with:
```
[db_check] ALL CHECKS PASSED. Infrastructure is ready for Phase 2.
```

If this fails, **stop here and fix it** before moving on — nothing downstream
will work if this doesn't pass.

### 4. Create the Kafka topic (first time only)

Redpanda usually auto-creates topics on first use, but to be safe, create it
explicitly:

```bash
docker exec -it streamguard-redpanda rpk topic create raw-events
docker exec -it streamguard-redpanda rpk topic list
```

You should see `raw-events` listed.

### 5. Prove the Kafka pipe works end-to-end

Open **two terminals**.

**Terminal A** — start the consumer (it will sit and wait for events):
```bash
cd consumer
python consumer_skeleton.py
```

**Terminal B** — send fake test events:
```bash
cd consumer
python test_producer.py --count 20 --delay 0.3
```

**Expected result:** within a second or two of running the producer, Terminal
A should start printing lines like:
```
[consumer] [ok   ] #1  {'src': '192.168.1.7', 'dst': '10.0.0.3', 'timestamp': 1234567890, 'anomaly_score': 4.0, 'is_alert': True}
```

If you see this — **Phase 1 is complete.** The full pipe (Kafka → Consumer)
is proven to work, Postgres and Redis are verified, and the project is ready
to hand off for Phase 2.

---

## What Phase 2 needs to do (for whoever picks this up next)

Everything is marked with `# --- Phase 2 will add here: ---` comments inside
`consumer_skeleton.py`. In order:

1. **Replace `fake_score_event()`** with the real scoring function from
   Role 1 (Count-Min Sketch + chi-squared logic). Keep the same input/output
   shape — don't change the contract, just swap the internals.
2. **Add a `db_writer.py`** module with two functions:
   - `write_score(scored_event)` → inserts into the `scores` table
   - `write_alert(scored_event)` → inserts into the `alerts` table, returns
     the generated `alert_id`
   - Connection pattern to copy: see `db_check.py`, it already shows working
     insert statements for both tables.
3. **Add a `websocket_server.py`** module:
   - A basic WebSocket server (e.g. using the `websockets` Python library)
     listening on `config.WEBSOCKET_HOST:config.WEBSOCKET_PORT`
   - A `broadcast(alert)` function the consumer calls whenever a new alert
     is written — pushes `{"type": "alert", "data": {...}}` to all connected
     clients (per the agreed WebSocket message format)
4. **Swap `test_producer.py` out for the real DARPA replayer** (Role 2's
   script) once it's ready — same topic, same event shape, so nothing else
   needs to change.

---

## File reference

| File | Purpose |
|---|---|
| `docker-compose.yml` | Spins up Redpanda, Postgres (+TimescaleDB), Redis |
| `init-db/01_init.sql` | Auto-creates `scores` and `alerts` tables on first Postgres startup |
| `consumer/config.py` | All shared ports/hosts/topic names/threshold — change values here once, not scattered across files |
| `consumer/test_producer.py` | Sends fake events into Kafka — used only to prove the pipe works |
| `consumer/consumer_skeleton.py` | Reads events from Kafka, applies placeholder scoring, prints results — **this is what Phase 2 extends** |
| `consumer/db_check.py` | One-time script to verify Postgres + Redis are working correctly |

---

## Shutting down

```bash
docker compose down        # stop everything, keep data
docker compose down -v     # stop everything AND wipe all data (clean slate)
```
