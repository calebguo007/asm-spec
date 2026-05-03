**Table 5: Component ablations on the same 200-task suite as §6.5.**

| Ablation | Metric | Result | Interpretation |
|---|---|---:|---|
| Drop trust delta | Kendall's tau vs full TOPSIS | 0.95 | trust delta is a tiebreaker |
| TOPSIS vs weighted average | Kendall's tau | 0.6133 | top-1 disagreement 22.5% |
| io_ratio sweep | Min adjacent tau in swept range | 0.9833 | rankings stable across realistic I/O ratios |
