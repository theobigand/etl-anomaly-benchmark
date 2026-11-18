# Scientific command help descriptions

`research.temporal_decision.x_main__mutmut_2` (source SHA-256
`f402ba92cdbd8a143608f9ce9d1ab98f68cad5b6c881318f504ab8c0380742d8`) and
`research.multi_schema.x_main__mutmut_2` (source SHA-256
`1e2e1bb4869f59f8fdf1f19ab2762d96a75ca8aa939df4ec156324d9d7315ce4`)
remove their command descriptions. Direct executions of each generated mutant
with `--help` exit normally but omit the study's purpose and protocol link;
the original commands display both. The outputs are preserved as
`temporal_decision-help-{original,mutant}.txt` and
`multi_schema-help-{original,mutant}.txt` in
`evidence/continuation-2026-11-15/`.

This is a demonstrated user-facing difference. Add meaningful help-contract
regressions when the current native run has finished, then verify RED on each
mutant, GREEN on the originals, and the native engine's final verdict. These
are not yet verified kills and are not owner equivalence proposals.
