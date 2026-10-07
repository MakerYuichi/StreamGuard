# StreamGuard --- Real-Time Anomaly Detection over Streaming Graphs

StreamGuard is a real-time anomaly detection system for network traffic
represented as streaming graph events. It processes
`(source, destination, timestamp)` connection events, scores suspicious
communication patterns as the stream arrives, stores results, and
visualizes alerts through a live web dashboard.

> **Project status:** Phase 1 infrastructure, Phase 2 end-to-end
> integration, and the current evaluation/demo work are in place. The
> project is now focused on evaluation, packaging, presentation, and
> improving explainability/false-positive handling.

## 1. Project Overview

StreamGuard combines:

-   **Streaming ingestion** of network events
-   **Count-Min Sketch** for bounded-memory frequency estimation
-   **MIDAS-inspired streaming scoring** for burst/anomaly detection
-   **Kafka-compatible messaging through Redpanda**
-   **PostgreSQL/TimescaleDB** for scores and alerts
-   **WebSocket** delivery of live alerts
-   **React + D3.js** for interactive graph visualization
-   A **batch statistical baseline** for comparison

The project is not presented as a new anomaly-detection algorithm. The
contribution is the integration of streaming detection, storage, live
communication, visualization, and a matched batch-vs-streaming
evaluation workflow.

## 2. Detection Approach

For each streaming edge:

``` text
Source → Destination → Count → Historical Baseline → Score → Threshold → Alert
```

The streaming scorer maintains bounded state using Count-Min Sketch
structures and compares current activity with historical activity. A
high score indicates that an edge is behaving unusually relative to its
recent history.

The current implementation is **MIDAS-inspired/simplified**, rather than
a claim of reproducing every component of the original research system.

### Related work

-   **Count-Min Sketch** --- Cormode & Muthukrishnan (2005), used as the
    bounded-memory frequency-estimation structure.
-   **MIDAS** --- Bhatia et al. (AAAI 2020), the basis for the streaming
    anomaly-scoring approach.
-   **GraphSAGE** --- Hamilton et al. (NeurIPS 2017), relevant to future
    graph/neighbourhood-aware extensions.

We do not claim a new anomaly-detection algorithm. The engineering
contribution is the end-to-end streaming pipeline and its interactive
graph visualization and evaluation.

## 3. System Architecture

``` text
DARPA labelled data
        │
        ▼
Dataset Replayer
        │
        ▼
Redpanda / Kafka
        │
        ▼
Python Consumer + Streaming Scorer
        │
        ├──────────────► PostgreSQL / TimescaleDB
        │
        ▼
WebSocket Server
        │
        ▼
React + D3.js Dashboard
        │
        ├── Live graph
        ├── Metrics
        └── Alert feed
```

### Main components

  -----------------------------------------------------------------------
  Component                           Purpose
  ----------------------------------- -----------------------------------
  `data/`                             DARPA processed data and
                                      ground-truth labels

  `ingestion/`                        Replays network events into the
                                      streaming pipeline

  `algorithm/`                        Count-Min Sketch and streaming
                                      scoring logic

  `consumer/`                         Kafka consumer, scoring, database
                                      writes and WebSocket integration

  `frontend/`                         React/D3 live dashboard

  `baseline/`                         Batch baseline and
                                      comparison/evaluation scripts

  `docker-compose.yml`                Starts Redpanda,
                                      PostgreSQL/TimescaleDB and Redis
  -----------------------------------------------------------------------

Redis is provisioned for future neighbourhood/cache work; it is not part
of the current core scoring path.

## 4. Current Implementation Status

### Phase 1 --- Infrastructure

Completed:

-   Docker-based infrastructure
-   Redpanda/Kafka-compatible broker
-   PostgreSQL/TimescaleDB
-   Redis provisioning
-   Database schema and connectivity checks
-   Initial frontend scaffold
-   Initial batch baseline

### Phase 2 --- End-to-End Pipeline

Completed:

-   DARPA data replay
-   Streaming consumer
-   Count-Min Sketch based scoring
-   Database score and alert writes
-   WebSocket alert broadcasting
-   React/D3 live dashboard
-   Batch-vs-streaming comparison workflow
-   Matched ground-truth evaluation

### Frontend / Visualization

The dashboard currently provides:

-   Live connection status
-   Streaming metrics
-   Force/deterministic graph visualization
-   Source-destination relationships
-   Alert highlighting
-   Live alert feed
-   WebSocket-driven updates

The frontend is intended to make backend detection results
understandable visually rather than replacing the detection engine.

## 5. Evaluation Results

The current evaluation uses a matched subset of the DARPA data so that
batch and streaming results are evaluated against the same events and
ground truth.

### Evaluation subset

-   **Rows:** 350,001--450,000
-   **Events:** 100,000
-   **Anomalous events:** 50,893
-   **Normal events:** 49,107
-   **Unique `(src, dst)` edges:** 5,650
-   **Unique attack edges:** 1,057
-   **Time span:** 3,525 seconds

### Threshold sweep

  --------------------------------------------------------------------------
       Streaming   Unique edges True positives      Precision         Recall
       threshold        flagged                               
  -------------- -------------- -------------- -------------- --------------
               3          5,614          1,057          0.188          1.000

             300          3,274          1,055          0.322          0.998

           1,000          1,500            994          0.663          0.940

           3,000            797            752          0.944          0.711

          10,000            751            747          0.995          0.707
  --------------------------------------------------------------------------

The threshold sweep shows the expected precision-recall trade-off. The
as-run threshold of `3` is highly sensitive and therefore produces many
false alerts. A threshold around `1,000` gives a more balanced operating
point for the current subset.

### Threshold-free metric

-   **AUC: 0.968**

This is the safest single summary metric for the current
threshold-independent evaluation.

### Detection delay

At the highly sensitive streaming threshold used for the real-time
demonstration, most comparable attack edges produced same-event alerts.
The streaming system is therefore able to react without waiting for a
complete batch window.

The batch baseline operates on a 10-second window, so its detection is
inherently bounded by that windowing approach.

## 6. Important Limitations

The current system should not be described as a production-ready
security detector.

Current limitations include:

-   The streaming threshold is sensitive and can generate many false
    positives.
-   The current graph highlights suspicious/alerted relationships but
    does not yet provide full explainable-AI reasoning.
-   `subgraph_nodes` currently contains the source and destination; a
    full k-hop confirmation stage is not implemented.
-   The evaluation uses a matched subset rather than the full 4.5M-row
    DARPA file because the naive batch baseline becomes expensive as
    history grows.
-   The current scorer is a simplified/MIDAS-inspired implementation and
    should not be presented as a new algorithm.

## 7. Next Phase

### Evaluation and reliability

-   Finalize the matched evaluation configuration.
-   Freeze the reported metrics and comparison plots.
-   Continue threshold tuning based on the precision-recall trade-off.
-   Validate the live demo using the same reproducible configuration.

### Explainability

Planned improvements include showing why an alert was raised, such as:

-   Current activity
-   Historical activity
-   Baseline expectation
-   Anomaly score
-   Threshold
-   Source-destination context
-   Alert severity

### Graph-aware analysis

Future work can include:

-   k-hop neighbourhood confirmation
-   Suspicious subgraph analysis
-   Top anomalous nodes/edges
-   Alert aggregation
-   Timeline and filtering
-   More detailed graph-level explanations

## 8. Quick Start

### 1. Start infrastructure

``` bash
docker compose up -d
docker compose ps
```

Confirm the required services are healthy.

### 2. Start the consumer

``` bash
cd consumer
python consumer_v2.py
```

The consumer starts the WebSocket server, connects to Kafka/Redpanda,
scores events, writes results, and reports processing/alert throughput.

### 3. Start the frontend

``` bash
cd frontend
npm run dev
```

Open:

``` text
http://localhost:5173
```

### 4. Replay the dataset

For the current demo configuration:

``` bash
cd ingestion
python darpa_replayer.py ../data/darpa_subset.csv --rate 200 --no-header
```

The dashboard should receive alert updates through the WebSocket
connection.

### 5. Run the comparison

``` bash
cd baseline

python compare_final.py ../data/darpa_subset.csv \
    --no-header \
    --ground-truth ../data/darpa_ground_truth_subset.csv \
    --window 10 --zthresh 2.5
```

## 9. Repository Structure

``` text
Capstone-phase1/
│
├── algorithm/
│   ├── count_min_sketch.py
│   └── midas_scorer.py
│
├── baseline/
│   ├── baseline_batch.py
│   ├── compare_final.py
│   └── ground_truth.py
│
├── consumer/
│   ├── consumer_v2.py
│   └── websocket_server.py
│
├── data/
│   ├── darpa_processed.csv
│   └── darpa_ground_truth.csv
│
├── ingestion/
│   └── darpa_replayer.py
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── Graph.jsx
│   │   └── index.css
│   └── ...
│
├── docker-compose.yml
└── README.md
```

## 10. Team Contributions

  -----------------------------------------------------------------------
  Area                                Primary contribution
  ----------------------------------- -----------------------------------
  Infrastructure / scoring            Docker services, streaming scorer,
                                      Count-Min Sketch/MIDAS-inspired
                                      logic and consumer pipeline

  Evaluation                          Matched-subset evaluation,
                                      comparison scripts and
                                      precision/recall/delay analysis

  Frontend / visualization            React/D3 dashboard, WebSocket
                                      integration, graph visualization,
                                      metrics and alert feed

  Demo / integration                  End-to-end pipeline execution and
                                      live demonstration

  Documentation                       Report, presentation, figures,
                                      screenshots and project packaging
  -----------------------------------------------------------------------

All components are integrated as one team project; individual ownership
refers to the main area of contribution, not the entire system.

## 11. References

1.  Cormode, G., & Muthukrishnan, S. (2005). *An Improved Data Stream
    Summary: The Count-Min Sketch and its Applications.*
2.  Bhatia, S., Hooi, B., Liu, Y., Stein, A., Chalapathy, R., &
    Faloutsos, C. (2020). *MIDAS: Microcluster-Based Detector of
    Anomalies in Edge Streams.* AAAI.
3.  Hamilton, W., Ying, Z., & Leskovec, J. (2017). *Inductive
    Representation Learning on Large Graphs.* NeurIPS.
