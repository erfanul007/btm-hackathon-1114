# Break the Model — our team submission

Work for the Alignment Security Hackathon "Break the Model" challenge (target:
Riley, the AI front desk of a fictional hospital). **All data is fake.**

> **For the teammate merging everything:** start at
> [`docs/SUBMISSION.md`](docs/SUBMISSION.md) — it's the full hand-off (findings,
> honest caveats, repo map, reproduce steps, submittable turn_ids, and the TODO
> list). This repo is self-contained and runnable.

## What's here (our contribution)

| File | What |
|---|---|
| `attacks.py` | 23 attacks as `{name, messages}`, grouped by hypothesis H1–H13 |
| `harness.py` | Batch runner: each attack ×N, fresh convo, throttled, scored |
| `defense.py` | Deterministic **egress PII filter** (our mitigation) — decodes base64/hex before scanning |
| `report.py`, `recon*.py`, `schema_recon.py` | Aggregation + benign recon |
| `docs/SUBMISSION.md` | **Start here** — the hand-off |
| `docs/writeup.md` | One-page findings |
| `docs/slides.html` | 9-slide, 3-minute deck |
| `docs/heatmap.html` | Attack × model leak-rate heatmap |
| `docs/schema.md` | Confirmed DB schema + ER diagram |
| `results/` | Measured runs (`runs.jsonl` + summary `.txt`) |

## Headline

We attacked the **hardest tier, Level 3** (the server only serves Level 3).
Legitimate-task requests (name lookup 100%, id enumeration 90%) extract all 413
patients' core PII; the Level-3 code lock holds for auxiliary tables but not for
patient demographics. Our `defense.py` egress filter catches it (precision 96%,
recall 79% over 1,313 turns) — and the decode upgrade even revealed a hex-encoded
leak our own harness had scored as safe.

## Quickstart

```bash
python3 setup.py                 # your own name + Nebius key (writes .env, gitignored)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python harness.py -a lookup_by_name_broad -m all -n 20
.venv/bin/python report.py
```

## Credit

Base kit (`setup.py`, `chat.py`, `btm.py`, `example_attack.py`, original
`README` content) is from **natalienma/break-the-model-starter**. Everything in
the table above and in `docs/` is our team's work.
