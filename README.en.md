# EVE-LM: a **failed** experiment — training an EVE Online Chinese model from scratch on a 4 GB laptop GPU

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](requirements.txt)
[![Status](https://img.shields.io/badge/status-failed-red.svg)](#why-it-failed)

Chinese version: [README.md](README.md) · Repo: <https://github.com/MC5lan/EVEonlie-LLM>

---

## Why it failed

**This is a failed project.** Not "could be better" — the approach itself did not work.

| What I wanted | What I got |
|---|---|
| An assistant that understands EVE | A lookup tool that copies fields |
| "Recommend a ship for tier-4 Abyssal runs" | A raw paragraph with a note "excerpt, not summarized" |
| A model that understands EVE content | A model that only paraphrases given text |
| 100% end-to-end means it works | 100% on my own 200 questions; **7/7 wrong** on real ones |

**The most damning comparison:**

```
With guards   100.0%   ← system capability, almost entirely deterministic code
Raw model      69.5%   ← actual model ability

Of which the model can only:
  copy fields           94%
  list fit slots       100%

And cannot:
  count ships            0%
  summarize lore        20%
  decide when to refuse 10%
```

A 35.4M-parameter model that has seen 4.25M tokens **cannot "understand" anything**.
It can phrase "shield capacity 3200 HP" fluently, but it has no idea what that means.

Full postmortem: [docs/WHY-IT-FAILED.md](docs/WHY-IT-FAILED.md) (Chinese)

All 62 decisions: [docs/DECISIONS.md](docs/DECISIONS.md) (Chinese)

---

## About "this was written by an AI"

**Every line of code, every document, every eval, every data analysis in this repo was produced by an AI agent.**

The human: set direction, reviewed results, rejected wrong turns, said "continue".
The AI: wrote code, built datasets, tuned hyperparameters, wrote docs, ran evals, fixed bugs —
including finding its own label-alignment bug.

What that means, honestly:

- **Consistent style but no "feel"**. Many places follow the rule rather than "this must be this way here".
- **Failures are recorded, but not all failures were found**. The 100% eval was self-authored —
  that trap catches agents and humans alike.
- **Lots of engineering, little insight**. The 18 pitfalls are real, but mostly implementation details,
  not understanding of what EVE players actually need.

Treat it as **a measurement of how far an AI can go on its own**, not as an EVE tool.

---

## Usage disclaimer

```
✅ Fine for: learning the full RAG + small-model pipeline; reading 18 pitfalls; copying eval/guard patterns
❌ Do not:  treat as authoritative EVE data; use as a product base; trust any open-ended advice
⚠️  All numbers must be verified against the SDE; this repo may be outdated or wrong
```

Environment: RTX 3050 Laptop / 4 GB VRAM / single machine / no external LLM API.

---

## What it can actually do

> A **lookup assistant**, not an advisor.
> Can answer: a ship's attribute, a fit's slot contents, how many ships in a class, what an entity is.
> Cannot answer: "recommend a fit for me", "how should a new player plan".
> Those return an explicit "excerpt, not summarized" instead of pretending.

---

## 1. Final state

| Item | Value |
|---|---|
| Parameters | 35.4M (d_model 384 / 16 layers / 8 heads, GQA 4 groups / d_ff 1024 / vocab 24576) |
| Tokenizer | self-trained BPE, 24,576 vocab, **2.25 chars/token** |
| Corpus | 654 docs / 925,585 chars rewritten / **4,252,169 tokens** |
| Structured assets | 7,591 SDE cards / 359 fits / 426 ships / 48 classes / 62 lore entries |
| Index | 24,500 chunks, bge-small-zh 512-d, α=0.55 |
| Pretraining | val 2.87 (step 3000, best before overfitting) |
| SFT | val 0.0209, 10,555 QA pairs |
| **End-to-end eval** | **200 questions: 100% with guards / 69.5% raw model** |
| **Retrieval eval** | **recall@1 81.7% / recall@10 97.7% / MRR 0.882** |

---

## 2. Architecture

```
Question
   │
   ├─ Dialogue state (rag/dialogue.py) ── coreference: "and its mid slots?" → "Dominix mid slots"
   │
   ├─ Deterministic routing (rag/local_model.py)
   │    ├─ out-of-scope / price / unknown field → refuse without calling the model
   │    ├─ acronyms (T3C / MWD…)               → table lookup
   │    ├─ ship class / lore entity            → index lookup
   │    ├─ comparison ("A vs B")               → list both, make no judgement
   │    ├─ attribute question                  → SDE compact context → model → number check
   │    ├─ fit question                        → fit slot context → model
   │    └─ everything else                     → structured excerpt (source + best sentence)
   │
   └─ Three guards
        ├─ missing-field detection (before the model)
        ├─ closed-set number verification (after generation)
        └─ deterministic SDE fallback (template overrides a wrong number)
```

**Core split: the model handles phrasing, never facts.**

---

## 3. Quick start

```bash
# single-turn
python -m rag.local_model --query "毒蜥级的护盾容量是多少"

# multi-turn CLI
python -m rag.dialogue

# HTTP + web UI
python -m serve.api --port 8000     # open http://127.0.0.1:8000

# end-to-end eval (200 questions)
python -m eval.run_eval

# model only, guards off
python -m eval.run_eval --no-guard

# retrieval eval
python -m eval.eval_retrieval --n 300
```

Dependencies: `torch` (CUDA build), `onnxruntime`, `tokenizers`, `fastapi`, `uvicorn`.

---

## 4. Key decisions

### 4.1 Why only 35M parameters

On 4 GB VRAM, 35M is what full-parameter training can hold (batch 2 × 1024 seq, bf16, 1.7 GB).
Bigger models do not pay off at 4.25M tokens — Chinchilla ratio is ~20 tokens/param, we are already
near it; larger would just overfit faster.

### 4.2 Why answers come from structured data, not model memory

Measured: asked from memory for Gila's shield capacity, the model answered **235** (truth: 3200).

35M parameters cannot store attributes for 4,000+ ships and 4,000+ modules. So:

- numbers come from the SDE; anything outside the SDE is "I don't know"
- the model only turns a given number into fluent Chinese
- if it writes a wrong number, `FactContext.lookup()` overrides with the SDE value

### 4.3 Why classes and lore use table lookup

The raw model scores **0%** on "how many dreadnoughts are there" and **20%** on "what is X".
Counting and summarizing are far beyond 35M. Both answers are already in the indexes — lookups are 100%.

### 4.4 Why no reranker (negative result)

Downloaded bge-reranker-base (int8, 266 MB) as a cross-encoder:

| | recall@1 | recall@10 | MRR | Latency |
|---|---:|---:|---:|---:|
| baseline | **81.7%** | 97.7% | **0.882** | 21 ms |
| + rerank | 78.0% | 97.3% | 0.859 | +500 ms |

**Slower and worse.** Eval queries are excerpts of the target doc, so lexical overlap is already high;
the cross-encoder adds nothing and gets confused by versioned duplicates.
Code kept in `rag/rerank.py`, disabled by default.

### 4.5 Why the eval reads 100%

The 200 questions were generated from the system's existing capabilities
(facts / fits / classes / lore / refusal / missing-field).
**They do not represent open-ended real questions.**

Real colloquial questions ("fit me a ship for tier-4 Abyss") score far lower — that category is not covered.

---

## 5. Training

```
Pretraining  10,200 steps planned → stopped at 3,000 (val 2.87)
             at 5,000 val rose to 3.35: clear overfitting
             4.25M tokens; 20 epochs means memorizing

SFT          3 epochs, 10,555 pairs, val 0.0209
             loss on assistant tokens only; user tokens labeled -100
             labels MUST be shifted right (the model's loss does not shift)
```

**Measured overfitting**: the step-5000 model recites the corpus fluently while answering the wrong question.

---

## 6. Known defects

| Defect | Status |
|---|---|
| Unstable long-number copying | 9999 becomes 907 — covered by SDE fallback |
| 1,024 context | long fit answers truncated to 512 |
| Weak open-ended answers | excerpts only, no summarization |
| Mediocre sentence picking in guides | many title-style fragments |
| Fitting solver | 359 fits pass, but T3 subsystem skills and command bursts unimplemented |
| Lore | 62 entries out of 66 entities; the rest are mentioned too rarely |

---

## 7. Layout

```
canonical/          654 normalized docs
  ├─ 02_舰船与装配/装配库/        359 fits
  ├─ 08_剧情与世界观/词条/        62 lore entries
  └─ _topic_*/                    class index, lore index
data/               sde_facts.jsonl (7,591), fits.jsonl, sft.jsonl, token shards
index/              retrieval index (24,500 chunks)
tokenizer/          self-trained BPE
ckpt/               base.pt, sft.pt
src/                model.py, muon.py, train.py, sft_train.py
rag/                retriever.py, local_model.py (guards + routing), dialogue.py, compose.py
serve/              api.py (FastAPI + single-page UI)
eval/               run_eval.py (200 Q), eval_retrieval.py, report_*.txt
tools/              corpus builder, SDE export, fit parser, eval generator
```

---

## 8. Eval history

```
eval/report_baseline.txt    59.5%   initial
eval/report_v2..v15.txt     75.5% → 100%   iterative fixes
eval/retrieval_baseline.txt recall@1 81.7% / @10 97.7%
eval/retrieval_rerank.txt   78.0%   rerank (rejected)
```

Two "improvements" that made things worse were caught by the eval:

- single-field context: 94% → 93%
- asked field moved to the end: 94% → 78%

**Without the eval, both would have shipped as optimizations.**

---

## Other docs (Chinese only)

- [docs/TIMELINE.md](docs/TIMELINE.md) — 8 development phases
- [docs/PITFALLS.md](docs/PITFALLS.md) — 18 pitfalls, symptom → cause → fix
- [docs/EVAL.md](docs/EVAL.md) — all metrics and how to reproduce
- [docs/WHY-IT-FAILED.md](docs/WHY-IT-FAILED.md) — the postmortem
- [docs/DECISIONS.md](docs/DECISIONS.md) — all 62 decisions with post-hoc ratings
- [docs/ROADMAP.md](docs/ROADMAP.md) — open questions
