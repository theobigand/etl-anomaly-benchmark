#!/bin/bash
cd "/Users/theo/Developer/school/esilv/Master Thesis Bootcamp/etl-anomaly-benchmark"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
/Users/theo/miniconda3/envs/etl-benchmark/bin/python research/labelled_benchmark.py --seeds 5 6 7 8 9 --methods deep --workers 9 --resume --output verification/evidence/validity/seeds_5_9/deep
/Users/theo/miniconda3/envs/etl-benchmark/bin/python research/label_sensitivity.py --methods deep --workers 9 --output verification/evidence/validity/label_rules/deep
echo ALL_DONE
