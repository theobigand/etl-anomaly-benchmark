# Chronological study with controlled fault injection on unlabelled time series: protocol (issue #78)

Written and archived before any result of this study exists.

## Question

Only four labelled catalog tables have a verified time variable, so every chronological conclusion
rests on four tables. Several unlabelled UCI tables record real, regularly sampled time series.
They carry no anomaly truth, and none is invented here. What they can measure is the cost of real
temporal change for a detector: how many clean future rows a detector fitted on the past flags,
and how well it finds faults injected into the future, compared with a random split of the same
rows.

## Tables

UCI tables whose time variable is a real, single-series timestamp, read with the format stated in
the code (`TIME_SPECS`): Air Quality (360), Appliances Energy Prediction (374), Bike Sharing (275),
Seoul Bike Sharing Demand (560), Single Elder Home Monitoring (799), Power Consumption of Tetouan
City (849), Steel Industry Energy Consumption (851) and Istanbul Stock Exchange (247).
Dow Jones Index (312) and Productivity of Garment Employees (597) are panels of several entities per
date, not one series, and are excluded. Forest Fires (162) has only a month. A table is used when it
has at least 1,500 rows and four continuous columns (at least 10 distinct values) after removing the
time columns and every column with a rank correlation above 0.99 with time (index and counter
columns). The rows are sorted by the parsed timestamp; whether the file was already in order is
recorded. No timestamp is created.

## Arms

Rows with a missing value in a continuous column are dropped, exact duplicates removed, and tables
longer than 20,000 rows thinned by a regular stride that keeps the order. Each table is evaluated in
two arms on the same rows:

- chronological: first 60 % of the rows for fitting, last 40 % for evaluation;
- random: a seeded random 60/40 partition of the same rows.

The six typed faults of `injection.py` (rate 3 % per type, severity 1) are injected into the
evaluation rows only, with all magnitudes read from the fitting rows. Detectors are fitted on the
fitting rows (clean, no label) with contamination 0.05, the alert rate of the ETL experiments. The
drift detector is left out because its time column is synthetic after injection. Seeds 42, 1, 2, 3,
4 (the chronological partition is the same for every seed; the seed drives the injection and the
random arm).

## Measures

Per detector and arm: false-positive rate on the clean evaluation rows, recall per fault type. The
quantity of interest is the paired difference chronological minus random, per table, then the median
over tables with a bootstrap interval over tables. Tables are the units; rows and seeds are not.

## Hypotheses

- C1: the false-positive rate on clean rows is higher in the chronological arm than in the random arm
  for the median detector (real temporal change is flagged as anomalous).
- C2: recall of the injected faults changes by less than the false-positive rate (the faults are
  much farther from the fitted data than natural change).
- C3: the ranking of detectors by recall is stable between the arms.

A result that contradicts a hypothesis is reported as it is.
