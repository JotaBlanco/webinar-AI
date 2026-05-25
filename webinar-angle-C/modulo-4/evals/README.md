# evals/ — verification component (5)

Two computational sensors, one inferential.

- `schema_check.py` — validates every CSV your variant produces (required columns, no NaNs, residual sign convention, physical bounds, sample rate). Run on every regenerated CSV.
- `baseline_rmse.py` — reproducible baseline RMSE numbers per platform. Run *before* you propose anything, and compare your reported numbers against it.
- `consistency_judge.md` — LLM-as-judge spec for the final REPORT.md. Computational sensors run first; the judge is reserved for things only an LLM can score.

Rule of thumb: computational first, inferential where it earns it.
