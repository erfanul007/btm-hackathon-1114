"""Batch attack harness for Break the Model.

Runs each attack in attacks.ATTACKS N times (fresh conversation each run),
scores every response with the deterministic leak detector in defense.py, and
reports a success rate per attack per model. This is the "reproducible and
measured, not a one-off lucky result" evidence the judges ask for.

Usage:
    .venv/bin/python harness.py                      # all attacks, default model, 10 runs
    .venv/bin/python harness.py -n 20                # 20 runs each
    .venv/bin/python harness.py -m openai/gpt-oss-120b
    .venv/bin/python harness.py -m all               # every attack on every listed model
    .venv/bin/python harness.py -a leak_schema       # only the attack named leak_schema

Results are appended to results/runs.jsonl and a summary table is printed.
Every run is still logged by btm.py to logs/my_attempts.jsonl as well.
"""
import argparse, json, time
from pathlib import Path

import btm
import defense
from attacks import ATTACKS

# The server caps at 30 requests/minute. Space calls out and back off on 429 so
# results aren't polluted by rate-limit errors.
MIN_INTERVAL = 2.2          # seconds between requests (~27 rpm, under the 30 cap)
_last_call = [0.0]


def throttled_chat(message, model, conversation_id, retries=5):
    for attempt in range(retries):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()
        try:
            return btm.chat(message, model=model, conversation_id=conversation_id)
        except RuntimeError as e:
            if "429" in str(e) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))   # linear backoff: 5s, 10s, ...
                continue
            raise

# Judged models per the hackathon slides: Gemma 3 27B, DeepSeek V4 Pro,
# Claude Haiku 5.5, Claude Sonnet 5.5. As of now the server only serves DeepSeek
# V4 Pro of those (Gemma + Claude not available yet — confirm with organizers).
# So -m all targets just the judged model that's live; pass -m <id> for others.
MODELS = [
    "deepseek-ai/DeepSeek-V4-Pro-0813",       # judged, available
    # "google/gemma-3-27b-it",                # judged, NOT on server yet
    # "groq/qwen/qwen3.8-27b",                # 27B stand-in (Qwen, not Gemma)
]

# Full roster we already measured once (results/all_models_clean.txt):
ALL_MODELS = [
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "openai/gpt-oss-120b",
    "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "deepseek-ai/DeepSeek-V4-Pro-0813",
]

RESULTS = Path(__file__).parent / "results" / "runs.jsonl"
RESULTS.parent.mkdir(exist_ok=True)


def run_attack(attack, model):
    """Run one attack once. An attack is a list of user messages sent in sequence
    within a single conversation. Returns (verdict, last_turn_id, last_reply)."""
    conv = btm.new_conversation()
    reply, tool_calls = "", []
    for msg in attack["messages"]:
        reply = throttled_chat(msg, model=model, conversation_id=conv)
        # btm.chat doesn't return tool_calls; re-read them from the log tail.
        tool_calls = _last_tool_calls()
    verdict = defense.scan_response(reply, tool_calls)
    return verdict, btm.LAST_TURN_ID, reply


def _last_tool_calls():
    """Pull tool_calls from the most recent line btm.py just wrote."""
    try:
        line = btm.LOG.read_text().strip().splitlines()[-1]
        return json.loads(line)["response"].get("tool_calls") or []
    except Exception:
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=10, help="runs per attack (default 10)")
    ap.add_argument("-m", default=MODELS[0], help="model id, or 'all'")
    ap.add_argument("-a", default=None, help="run only the attack with this name")
    args = ap.parse_args()

    models = MODELS if args.m == "all" else [args.m]
    attacks = [a for a in ATTACKS if args.a is None or a["name"] == args.a]
    if not attacks:
        raise SystemExit(f"No attack named {args.a!r}. Names: {[a['name'] for a in ATTACKS]}")

    rows = []
    for model in models:
        for attack in attacks:
            hits, turn_ids, refusals, errors = 0, [], 0, 0
            for i in range(args.n):
                try:
                    verdict, turn_id, reply = run_attack(attack, model)
                except Exception as e:  # noqa: BLE001
                    errors += 1
                    print(f"  [{attack['name']} @ {model}] run {i+1} error: {e}")
                    continue
                if verdict.leaked:
                    hits += 1
                    turn_ids.append(turn_id)
                if verdict.refused:
                    refusals += 1
                mark = verdict.summary()
                print(f"  [{attack['name']} @ {model.split('/')[-1]}] run {i+1}/{args.n}: {mark}")
                _record(model, attack, verdict, turn_id, reply, i)
            rate = hits / args.n if args.n else 0
            rows.append((attack["name"], model, hits, args.n, refusals, errors, rate, turn_ids))

    print("\n=== SUMMARY ===")
    print(f"{'attack':22} {'model':34} {'leaks':>7} {'refuse':>7} {'err':>4} {'rate':>6}")
    for name, model, hits, n, refusals, errors, rate, _ in rows:
        print(f"{name:22} {model.split('/')[-1]:34} {hits:>3}/{n:<3} {refusals:>7} {errors:>4} {rate:>5.0%}")
    print("\nSuccessful turn_ids (submit these in the form):")
    for name, model, hits, n, refusals, errors, rate, turn_ids in rows:
        if turn_ids:
            print(f"  {name} @ {model.split('/')[-1]}: {', '.join(turn_ids[:5])}" + (" ..." if len(turn_ids) > 5 else ""))
    print(f"\nFull per-run records: {RESULTS}")


def _record(model, attack, verdict, turn_id, reply, i):
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "attack": attack["name"], "model": model, "run": i,
        "leaked": verdict.leaked, "refused": verdict.refused,
        "findings": [[l, s] for l, s, _ in verdict.findings],
        "turn_id": turn_id, "reply_preview": (reply or "")[:300],
    }
    with RESULTS.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
