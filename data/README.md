# StreamGuard — Dataset Downloads

This directory is **gitignored** (except this README and `*.gitkeep` markers).
Download each dataset manually and place the files here.

## CIC-IDS2017 (Primary)

**URL:** <https://www.unb.ca/cic/datasets/ids-2017.html>

Download the pre-processed CSVs (GeneratedLabelledFlows.zip).  
Required columns: `Source IP`, `Destination IP`, `Timestamp`, flow features, `Label`.  
Place the files in `data/cic-ids2017/`.

## UNSW-NB15 (Secondary)

**URL:** <https://research.unsw.edu.au/projects/unsw-nb15-dataset>

Download the CSV files from the UNSW research portal.  
Place the files in `data/unsw-nb15/`.

## DARPA 1998 (Legacy — regression tests only)

**URL:** <https://www.ll.mit.edu/r-d/datasets/1998-darpa-intrusion-detection-evaluation-dataset>

The processed files (`darpa_processed.csv`, `darpa_ground_truth.csv`,
`darpa_subset.csv`, `darpa_ground_truth_subset.csv`) are already tracked in
`data/` for regression tests only.  Do not use them as the primary evaluation
dataset (no IP addresses in the original raw form; the processed versions here
are synthetic).

## NSL-KDD

**Not used.** NSL-KDD has no source/destination IPs or timestamps, so it cannot
feed the streaming graph model.
