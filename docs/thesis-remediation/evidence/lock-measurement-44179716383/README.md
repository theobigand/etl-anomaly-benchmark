# Mutation measurement under the hash-locked environment

Hosted run 44179716383 (workflow `mutation-shards`, 45 shards, fresh mutants) at commit
`d3abc54fe99d616787102e2bf37527616fdb7f03`. Every shard installed from `install_locked.sh`
(pandas 3.0.6, pyod 3.6.7, numpy 2.4.6, scikit-learn 1.9.1, scipy 1.17.1, great-expectations 1.24.0,
torch 2.15.0+cpu). Shard 10 failed once on a network error during installation and passed on its rerun.
The run's own aggregation is expected to fail: the equivalence records still bound pandas 3.1.1 at that commit.

`outcomes.json` maps each of the 35,253 mutant identities to its native outcome
(34,786 killed, 463 survived, 4 timeout). All 101 accepted equivalence records and the 5 inconclusive LSTM
records survived. The full shard archives (3.6 GB) stay in the run's artifacts.
