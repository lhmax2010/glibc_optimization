# Host analysis tools

`trimmable_estimator.py` reads glibc `malloc_info` XML and estimates the byte
capacity of whole 4 KiB pages wholly contained in the reported `<size>` free
chunks. The lower bound uses each bucket's `from` size with worst alignment;
the upper bound uses `to` with best alignment. `<unsorted>` is reported as an
excluded diagnostic and is not silently folded into the estimate.

```sh
python3 tools/analysis/trimmable_estimator.py malloc_info.xml
python3 tools/analysis/trimmable_estimator.py --format tsv malloc_info.xml
python3 tools/analysis/validate_trimmable_estimator.py \
  data/raw/trimmable_estimator_20260905/cases.tsv \
  --output /tmp/trimmable-validation.tsv
cmp /tmp/trimmable-validation.tsv \
  data/raw/trimmable_estimator_20260905/validation.tsv
python3 tools/analysis/test_trimmable_estimator.py
```

The estimate is geometric capacity, not a prediction of `malloc_trim(0)`.
Addresses, top-chunk identity, heap layout, page residency, and arena reclaim
eligibility are absent from `malloc_info` histograms.
