# Demo reproduction compact evidence

This directory contains a machine-readable transcription of already published
release-phase tables. It does not add a measurement or recompute a board result.

- `batch_release_phase.tsv` copies the three single-process rows from
  `docs/l6_gst_release_phase_probe.md` and the eight valid scale-test rows from
  `docs/l6_release_phase_scale.md`.
- The exact report values are retained so HQ can reproduce the rounded
  `48.9% / 1.36 MiB` presentation and verify that the same phenotype was run in
  eight concurrent processes using only the public repository.
