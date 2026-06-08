# cc12m-downloader

Downloads a representative subset of the Conceptual 12M (CC12M) dataset from source URLs up to a configurable size limit.

## Usage

Download the TSV file from the [official repository](https://github.com/google-research-datasets/conceptual-12m), set `TSV_PATH` to its location and run:

```bash
python download_cc12m.py
```

Stops automatically when the dataset reaches `MAX_SIZE_GB` (default: 250GB).

## Sampling Strategy

URLs are deduplicated, split into 100 equal sections, shuffled within each section, then interleaved in round-robin order. This ensures uniform coverage across the full dataset regardless of where the download stops.

## Output

```
cc12m/
    images/        ← downloaded images (named by URL hash)
    captions.tsv   ← successful image-caption pairs (filename \t caption)
```

