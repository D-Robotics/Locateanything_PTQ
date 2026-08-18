# fast_336 live USB /detect box summary

## Throughput and correctness

| Metric | Batch 1 | Batch 2 | Change |
| --- | ---: | ---: | ---: |
| Strict-window results | 940.00 | 1368.00 | +428.00 |
| Output FPS | 7.83 | 11.40 | +45.53% |
| Language batch cycles | 940.00 | 684.00 | -256.00 |
| Mean results/cycle | 1.00 | 2.00 | +100.00% |

## Stage mean comparison

| Metric | Batch 1 mean | Batch 2 mean | Change |
| --- | ---: | ---: | ---: |
| Preprocess | 18.525 ms | 18.212 ms | -1.69% |
| Vision | 47.234 ms | 52.966 ms | +12.13% |
| Language | 127.570 ms | 174.807 ms | +37.03% |
| Postprocess | 0.015 ms | 0.010 ms | -31.63% |
| End-to-end record | 255.350 ms | 301.923 ms | +18.24% |

## Detailed stage statistics

| Profile | Metric | Mean | Median | P95 | Max | Samples |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Batch 1 | Preprocess | 18.525 ms | 18.498 ms | 18.944 ms | 20.216 ms | 940 |
| Batch 1 | Vision | 47.234 ms | 47.192 ms | 47.897 ms | 50.366 ms | 940 |
| Batch 1 | Language | 127.570 ms | 127.213 ms | 129.834 ms | 134.395 ms | 940 |
| Batch 1 | Postprocess | 0.015 ms | 0.014 ms | 0.016 ms | 0.062 ms | 940 |
| Batch 1 | End-to-end record | 255.350 ms | 254.827 ms | 259.056 ms | 263.942 ms | 940 |
| Batch 2 | Preprocess | 18.212 ms | 18.181 ms | 18.581 ms | 26.695 ms | 1368 |
| Batch 2 | Vision | 52.966 ms | 52.480 ms | 78.371 ms | 80.164 ms | 1368 |
| Batch 2 | Language | 174.807 ms | 174.433 ms | 177.315 ms | 181.145 ms | 1368 |
| Batch 2 | Postprocess | 0.010 ms | 0.015 ms | 0.018 ms | 0.046 ms | 1368 |
| Batch 2 | End-to-end record | 301.923 ms | 304.976 ms | 352.648 ms | 358.983 ms | 1368 |

## Resource comparison

For MemAvailable, the fourth and sixth numeric columns are minima; all other rows use maxima.

| Metric | Batch 1 mean | Batch 1 P95 | Batch 1 peak/min | Batch 2 mean | Batch 2 P95 | Batch 2 peak/min | Mean change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Process CPU | 74.28% | 79.00% | 107.00% | 91.31% | 97.00% | 106.00% | +17.03 pp |
| Process CPU / 18-core capacity | 4.13% | 4.39% | 5.94% | 5.07% | 5.39% | 5.89% | +0.95 pp |
| RSS | 174.56 MiB | 174.56 MiB | 174.56 MiB | 201.64 MiB | 208.44 MiB | 215.81 MiB | +27.08 |
| VmHWM | 174.69 MiB | 174.69 MiB | 174.69 MiB | 211.13 MiB | 215.81 MiB | 215.81 MiB | +36.44 |
| VSZ | 8056.94 MiB | 8056.94 MiB | 8057.50 MiB | 8613.11 MiB | 8613.19 MiB | 8613.75 MiB | +556.17 |
| System MemAvailable | 12133.22 MiB | 12147.30 MiB | 12104.50 MiB | 12101.55 MiB | 12115.84 MiB | 12071.62 MiB | -31.66 |
| BPU Core 0 | 80.31% | 90.30% | 100.00% | 84.22% | 95.00% | 100.00% | +3.92 pp |
| BPU Core 1 | 80.97% | 95.80% | 100.00% | 84.45% | 95.00% | 100.00% | +3.48 pp |
| BPU Core 2 | 80.75% | 94.20% | 100.00% | 84.61% | 94.70% | 100.00% | +3.86 pp |
| BPU Core 3 | 80.33% | 95.60% | 100.00% | 83.74% | 94.00% | 100.00% | +3.42 pp |
| Four-core BPU mean | 80.59% | 92.12% | 100.00% | 84.26% | 94.01% | 100.00% | +3.67 pp |
| DDR Read | 78.91 GiB/s | 107.18 GiB/s | 117.25 GiB/s | 71.81 GiB/s | 88.46 GiB/s | 97.64 GiB/s | -7.10 |
| DDR Write | 1.42 GiB/s | 2.65 GiB/s | 3.53 GiB/s | 9.55 GiB/s | 21.84 GiB/s | 23.52 GiB/s | +8.13 |
| DDR Read + Write | 80.33 GiB/s | 108.23 GiB/s | 118.96 GiB/s | 81.36 GiB/s | 91.28 GiB/s | 100.26 GiB/s | +1.03 |
| System ION CMA heap | 0.00 MiB | 0.00 MiB | 0.00 MiB | 0.00 MiB | 0.00 MiB | 0.00 MiB | +0.00 |
| System ION uncache heap | 302.06 MiB | 302.06 MiB | 302.06 MiB | 302.06 MiB | 302.06 MiB | 302.06 MiB | +0.00 |

## Sample counts

| Series | Batch 1 | Batch 2 |
| --- | ---: | ---: |
| Strict-window results | 940 | 1368 |
| One-second FPS windows | 120 | 120 |
| pidstat | 119 | 119 |
| Memory/ION | 223 | 223 |
| BPU | 95 | 94 |
| DDR paired tables | 2388 | 2370 |

- Batch 1 DDR interval: mean 50.228 ms, P95 51.428 ms, max 58.943 ms.

- Batch 2 DDR interval: mean 50.610 ms, P95 52.309 ms, max 57.531 ms.
