> Public archive note: application/process names are aliases. Host-side paths are sanitized; board runtime paths are retained. The frozen test-image BUILD_ID is intentionally public for reproducibility. Selected compact evidence is published under `data/raw/`; complete raw board evidence remains local and is available on request.

# Task: Adversarial audit of `docs/tizen_glibc_memopt_design_v1.md` + independent search for better levers

## Role

You are an independent reviewer with full read access to this glibc source tree
(Tizen `platform/upstream/glibc`, branch `tizen_base`). The document
`docs/tizen_glibc_memopt_design_v1.md` in this tree proposes memory
optimizations for Tizen TV (armv7l primary, aarch64 secondary). It was
produced by other AI models. **Assume it contains errors. Your job is to
find them — and to find better levers it missed.**

Optimization goal: reduce runtime RSS/PSS and flash footprint.
Hard constraint: no lever may cost more than **5–10%** performance on
allocation-heavy paths.

## Ground rules

1. **Verify in THIS tree, not from memory.** Every agreement, disagreement,
   or new proposal MUST cite file:line (or function + commit) in this
   checkout. If you rely on upstream-glibc knowledge from training, you must
   confirm it in this tree before using it. Claims without anchors will be
   discarded during consolidation.
2. **Attack the trust boundary first.** The doc's Section 2 declares claim
   T1 (Tizen delta vs upstream/2.40 limited to one memalign CVE patch in the
   malloc/nptl/locale/tunables paths) as unverified-by-reviewers. Re-derive
   it yourself: diff or log this tree against the `upstream/2.40` tag for
   `malloc/ nptl/ sysdeps/nptl/ sysdeps/pthread/ elf/dl-tunables* locale/
   iconv* packaging/`. Report any behavior-relevant delta the doc missed.
3. **Check the evidence, not just the prose.** For each doc claim you audit,
   open the cited file:line and confirm the code says what the doc says it
   says. A citation that exists but does not support the claim is a finding.
4. **32-bit armv7l is the primary target.** Wherever behavior differs by
   word size (arena formula, mmap threshold caps, VA pressure, struct
   sizes), state the armv7l-specific consequence explicitly.
5. **Do not soften verdicts.** "ALREADY-DEFAULT", "NOT-FEASIBLE", and
   "the doc is wrong here" are all acceptable outcomes.
6. **Read-only.** Do not modify any file in the tree.

## Part A — Audit the document (mandatory, do this first)

For every lever (L1–L10), every rejected item (R1–R7), every gate (G1–G2),
and trust claims (T1–T2), produce a verdict:

- **CONFIRMED** — you checked the cited code and the claim holds;
- **REFUTED** — the code says otherwise (show the anchor and the correct
  reading);
- **INCOMPLETE** — claim holds but omits a consequence that changes the
  risk/benefit (state it);
- **UNVERIFIABLE-FROM-SOURCE** — only if genuinely so; do not use this to
  avoid work.

Pay special attention to (known high-error-rate areas):
- L3: the exact conditions under which dynamic threshold adaptation is
  disabled, and what ELSE disables it as a side effect;
- L4/L5: tcache compile gating (`USE_TCACHE`) and whether any Tizen commit
  on any reachable branch changes tcache behavior at HEAD;
- R1: the top_pad default discrepancy between `elf/dl-tunables.list` and
  `mp_` initialization — confirm or refute the doc's resolution of it;
- T2: the `AT_SECURE` gating path for `GLIBC_TUNABLES`.

## Part B — Independent exploration (mandatory, at least equal effort)

Search this tree for memory levers the document does NOT contain. Do not
limit yourself to `GLIBC_TUNABLES`. Areas worth inspecting (non-exhaustive —
go beyond this list):

- allocator internals: heap growth policy (`sysdeps/**/malloc-sysdep*`,
  `arena.c` heap sizing/`HEAP_MAX_SIZE` on 32-bit), consolidation policy,
  `mremap` usage;
- per-thread costs: `struct pthread` layout, static TLS surplus
  (`glibc.rtld.optional_static_tls`), guard size defaults, TLS/DTV growth;
- dynamic loader: `ld.so` data structures, `dlconf` (Tizen-specific,
  enabled in spec) memory behavior, relro/bind-now interactions,
  `LD_DEBUG`-class residuals;
- libio/stdio buffering, wide-stream buffers, `open_memstream` behavior;
- resolver/NSS runtime allocations, `getaddrinfo` scratch buffers;
- locale/gconv runtime caching (`__gconv` cache, locale data mmap policy);
- string/memory routine selection on armv7l (ifunc tables, text size);
- packaging/spec: anything installed on the runtime image that the doc's
  Tier 4 missed; build flags with memory consequences;
- Tizen-specific patches anywhere in the tree with memory impact.

For each new lever: verdict (FEASIBLE / FEASIBLE-WITH-CAVEATS /
NOT-FEASIBLE / ALREADY-DEFAULT), evidence anchor, expected saving
(order of magnitude), perf cost estimate vs the 5–10% budget, rollout
method (env / code / spec / image), risk notes.

## Output contract (strict)

Write `docs/review_glibc_memopt_<your-model-name>.md`:

1. **Reviewer header**: model name, date, exact commit audited
   (`git rev-parse HEAD`), method summary (what you diffed/grepped/read).
2. **T1 re-derivation result**: your independent finding on the Tizen delta,
   with the command/evidence you used.
3. **Part A verdict table**: | Item | Verdict | Evidence (file:line) |
   Correction/consequence if not CONFIRMED |
4. **Top-3 challenges**: your three strongest objections to the document as
   a whole (design-level, not typo-level).
5. **Part B new-lever table**: same schema as the doc's Section 4 tables.
6. **negative_facts**: what you checked and confirmed absent/false, so the
   consolidator does not re-check it.
7. **cannot-verify list**: items requiring on-device measurement — name
   them, do not estimate numbers for them.

Do not summarize the document back. Do not pad. A short report full of
anchors beats a long report full of prose.
