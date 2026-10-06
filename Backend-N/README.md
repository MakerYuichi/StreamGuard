# StreamGuard backend

The backend project lives in `Backend-N/`; the React frontend is the sibling `frontend/` directory. Run backend commands from this directory unless a command says otherwise.

## Layout

- `docker-compose.yml`: Redpanda, TimescaleDB/Postgres, and Redis.
- `init-db/01_init.sql`: database schema initialization.
- `algorithm/`: bounded-memory Count-Min Sketch edge scoring.
- `consumer/`: shared config, Kafka consumer, Postgres writer, and WebSocket server.
- `ingestion/`: DARPA CSV replay into the `raw-events` topic.
- `baseline/`: batch comparison utilities.
- `data/`: downloaded CSVs; intentionally excluded from Git.

## Setup

```sh
cd Backend-N
python3 -m venv .venv
source .venv/bin/activate
# If the old kafka-python package is installed in this environment, remove it
# first; it shares the `kafka` import namespace with kafka-python-ng.
python -m pip uninstall -y kafka-python
python -m pip install -r consumer/requirements.txt
python -m pip install -r ingestion/requirements.txt
python -m pip install -r baseline/requirements.txt
docker compose up -d
```

The Postgres initialization scripts run only when the database volume is first created. To reinitialize from scratch, `docker compose down -v` removes the stored database contents.

Download the dataset files into `Backend-N/data/` (the DARPA MIDAS processed edge CSV and aligned ground-truth label CSV). For the source URLs used by this project:

```sh
mkdir -p data
curl -fL https://raw.githubusercontent.com/Stream-AD/MIDAS/master/data/darpa_processed.csv -o data/darpa_processed.csv
curl -fL https://raw.githubusercontent.com/Stream-AD/MIDAS/master/data/darpa_ground_truth.csv -o data/darpa_ground_truth.csv
```

Inspect their first lines and keep the original files unchanged. The scripts accept either a header row or headerless `src,dst,timestamp` columns; labels must be one row per event in matching order. Install baseline dependencies with `python -m pip install -r baseline/requirements.txt`.

Check the scoring module independently:

```sh
python -m algorithm.test_scorer
```

## Run the live pipeline

Open separate terminals, all in `Backend-N/` except the frontend terminal.

Terminal A, start the consumer (it also starts the WebSocket server):

```sh
python consumer/consumer_v2.py
```

Terminal B, replay headerless input at 200 events per second, up to 2,000 events:

```sh
python ingestion/darpa_replayer.py data/darpa_processed.csv --header no --rate 200 --limit 2000
```

If you want the original dataset timestamps instead of simulated replay time, add `--preserve-timestamps`. To attach the aligned labels to Kafka events, add `--ground-truth data/darpa_ground_truth.csv`.

Terminal C, launch the dashboard from the repository root:

```sh
cd ../frontend
npm install
npm run dev
```

The browser connects to `ws://localhost:8080`. The default host and port settings are in `consumer/config.py`.

## Batch baseline and database summary

From `Backend-N/`:

```sh
python baseline/baseline_batch.py data/darpa_processed.csv --no-header --window 10 --zthresh 2.5 --ground-truth data/darpa_ground_truth.csv
python baseline/compare_results.py
```

The batch script checks that the event and ground-truth files have matching row counts. The database summary excludes the schema's `test_src` initialization row. Database totals include previous runs unless the database is reset.

## Data and algorithm notes

The scorer is a Count-Min-Sketch-based burst heuristic inspired by MIDAS. It is not a full reproduction of the paper's microcluster detector. It decays historical counters at tick boundaries, so its sketch storage remains bounded; approximation error and integer decay affect the estimates. Alert threshold is `3.0` in `algorithm/midas_scorer.py` and should be tuned against labeled data before making accuracy claims.

The replayer defaults to simulated timestamps based on its send rate so events arrive in current time buckets. `--preserve-timestamps` instead uses column three (or the named `timestamp` column) from the dataset. Do not use it when the source timestamps are not Unix seconds.

## Stop services

```sh
docker compose down       # stop services, keep database volume
docker compose down -v    # stop services and delete database volume
```
