#!/usr/bin/env python3
"""Qwen-driven training orchestrator for evo_search2.py.

Loop executed on this machine:

  1. Build a context for Qwen: last run metrics, run history, the tail of
     training_log.csv, the current parameters.conf and Qwen's own
     AGENT_STRATEGY.md.
  2. Ask the local Ollama model for a new parameters.conf + AGENT_STRATEGY.md.
  3. Validate the proposal (locked keys untouched, ranges sane, max_guesses
     <= 6). One repair round is offered; otherwise the previous values stay.
  4. Persist the two files, snapshot them, and run evo_search2.py (the ONLY
     writer of pesos.csv) with a hard timeout.
  5. Archive everything of this iteration under qwen_training/logs/.
  6. STOP-CHECK: if the run reports 0 games that needed MORE than max_guesses
     guesses (Wordle rule: solving ON the last guess counts as solved;
     max_guesses <= 6), re-verify on the FULL word list before declaring the
     perfect game and finishing. --strict-cap restores the old stricter rule.

Qwen never touches the filesystem directly: the orchestrator extracts the two
fenced blocks from its reply and writes on its behalf. Everything else Qwen
says is archived but ignored.

Usage:
  python qwen_training/run_qwen_training.py --model qwen3.5-9b
  python qwen_training/run_qwen_training.py --dry-run --max-iterations 2
  python qwen_training/run_qwen_training.py --strict-cap  # 0 games >= max_guesses
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parent          # .../qwen_training
PROJECT_DIR = RUNNER_DIR.parent                        # folder holding evo_search2.py
EVO_SCRIPT = PROJECT_DIR / "evo_search2.py"
CONF_PATH = RUNNER_DIR / "parameters.conf"
STRATEGY_PATH = RUNNER_DIR / "AGENT_STRATEGY.md"
LOGS_DIR = RUNNER_DIR / "logs"
HISTORY_PATH = RUNNER_DIR / "history.jsonl"
FINAL_REPORT_PATH = RUNNER_DIR / "FINAL_REPORT.md"

sys.path.insert(0, str(RUNNER_DIR))
import conf_schema  # noqa: E402  (local module, single source of truth)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_text(path: Path, default: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def count_words(path: Path) -> int:
    return len({line.strip().lower() for line in read_text(path).splitlines() if line.strip()})


def resolve_dataset_dir(conf_values: dict) -> Path:
    dataset_value = str(conf_values.get("path_dataset_dir") or "")
    return (
        Path(dataset_value) if Path(dataset_value).is_absolute()
        else PROJECT_DIR / dataset_value
    ) if dataset_value else PROJECT_DIR / "dataset"


def resolve_word_source(conf_values: dict) -> Path:
    """Mirror of evo_search2's word-source resolution (for word counting)."""
    dataset_dir = resolve_dataset_dir(conf_values)

    def resolve(value: str, fallback_name: str) -> Path:
        if value:
            path = Path(value)
            return path if path.is_absolute() else PROJECT_DIR / path
        return dataset_dir / fallback_name

    termo = resolve(
        str(conf_values.get("path_termo_words") or ""),
        "words/termo_palavras_aceitas.txt",
    )
    if termo.exists():
        return termo
    return resolve(
        str(conf_values.get("path_accepted_words") or ""),
        "words/palavras_aceitas500.txt",
    )


def load_current_conf() -> tuple[dict, str]:
    """Parse parameters.conf (or synthesize defaults) -> (values, raw_text)."""
    raw = read_text(CONF_PATH)
    if raw.strip():
        values, errors = conf_schema.parse_conf_text(raw)
        if errors:
            print(f"WARNING: current {CONF_PATH.name} has problems: {errors}")
        values = {**conf_schema.DEFAULTS, **values}
    else:
        values, raw = dict(conf_schema.DEFAULTS), conf_schema.render_conf(conf_schema.DEFAULTS)
    return values, raw


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m{seconds % 60:02d}s" if seconds >= 3600 else f"{seconds // 60}m{seconds % 60:02d}s"


# --------------------------------------------------------------------------- #
# Ollama client (stdlib only)
# --------------------------------------------------------------------------- #

def ollama_list_models(base_url: str, timeout: int = 10) -> list[str]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [model.get("name", "") for model in data.get("models", [])]


def model_available(models: list[str], wanted: str) -> bool:
    def base(name: str) -> str:
        return name.split(":")[0].strip().lower()
    return any(base(name) == base(wanted) for name in models)


def ollama_chat(
    base_url: str,
    model: str,
    messages: list[dict],
    *,
    temperature: float,
    num_ctx: int,
    timeout: int,
    think: bool | None = None,
) -> str:
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    if think is not None:
        payload["think"] = think
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"]


# --------------------------------------------------------------------------- #
# Qwen reply parsing
# --------------------------------------------------------------------------- #

THINK_RE = re.compile(r"<think>(.*?)</think>", re.S | re.I)
FENCE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.S)


def split_thinking(text: str) -> tuple[str, str]:
    """Return (clean_body, thinking_text). Handles an unclosed <think> too."""
    thinking_parts = THINK_RE.findall(text)
    body = THINK_RE.sub("", text).strip()
    if "<think>" in body:  # model forgot to close the tag
        head, _, rest = body.partition("<think>")
        thinking_parts.append(rest)
        body = head.strip()
    return body, "\n\n---\n\n".join(part.strip() for part in thinking_parts)


def extract_blocks(body: str) -> tuple[str | None, str | None, bool]:
    """Extract the ```parameters``` and ```strategy``` fenced blocks.

    Returns (params_text, strategy_text, used_order_fallback).
    """
    blocks = [(label.strip().lower(), content) for label, content in FENCE_RE.findall(body)]
    params: str | None = None
    strategy: str | None = None
    for label, content in blocks:
        if params is None and any(word in label for word in ("param", "conf", "toml", "ini", "cfg")):
            params = content
        elif strategy is None and any(word in label for word in ("strat", "md", "markdown", "plan", "agent")):
            strategy = content
    used_fallback = False
    if (params is None or strategy is None) and len(blocks) == 2 and not any(label for label, _ in blocks):
        params, strategy = blocks[0][1], blocks[1][1]
        used_fallback = True
    return params, strategy, used_fallback


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #

SYSTEM_TEMPLATE = """You are the parameter-tuning agent for evo_search2.py, an evolutionary \
optimizer that tunes three scoring weights (pesos.csv) for a Termo (Brazilian Wordle) solver. \
You orchestrate experiments by choosing parameters; the script runs the actual simulations.

## Your write access (enforced by the orchestrator)
You may write EXACTLY two files, by including their full content in fenced blocks in every reply:
1. a ```parameters fenced block -> qwen_training/parameters.conf (COMPLETE file, every key)
2. a ```strategy fenced block   -> qwen_training/AGENT_STRATEGY.md (COMPLETE file)

## Hard rules
- parallel_workers and every path_* key are LOCKED: copy their current values unchanged. \
A proposal that changes them is rejected.
- max_guesses must stay <= 6.
- You NEVER write weights. pesos.csv is written only by evo_search2.py. To explore, change parameters.
- qwen_training/logs/, training_log.csv and pesos.csv are READ-ONLY evidence for you; \
the orchestrator digests them for you below.

## What the parameters mean
- The simulation plays one Termo game per word of the source word list. The current weights \
come from pesos.csv; the optimizer is a (1+1)-ES: it proposes weight deltas, evaluates them \
exactly, and keeps improvements. Grade = fail_penalty * games_over_max_guesses + average_guesses \
(lower is better), so removing failures beats shaving the average.
- step_fraction: the INITIAL radius of the ES proposals, as a fraction of ||weights||. \
BIGGER = larger jumps = MORE exploration. SMALLER = cautious local steps = LESS exploration. \
Lowering it does NOT make the search explore more - that is the opposite of how it works. \
After rule_window proposals the 1/5th rule adapts the step automatically, so step_fraction \
mainly sets how a run starts.
- rule_window / rule_target / rule_factor / min_step_fraction: the 1/5th success rule that \
adapts the step size. Every rule_window proposals: if the success rate is above rule_target \
the step grows by rule_factor, otherwise it shrinks; it never drops below min_step_fraction.
- fail_penalty: how much ONE over-threshold game outweighs differences in the average \
(lexicographic weight). Keep it large unless you deliberately want pure average minimization.
- seed: RNG seed of the ES proposals (NOT the word sample - that is sim_seed).
- sim_words: 0 = use ALL {total_words} words; N = a deterministic random sample of N words \
(seeded by sim_seed). Small samples (30-200) run fast. Only sim_words = 0 gives the real \
distribution - the orchestrator re-verifies any claimed success on the FULL list before \
stopping.
- sim_seed: seed of the word sample. KEEP sim_words and sim_seed FIXED while comparing runs: \
with the same sample every measurement is comparable, so improvements are real. Changing \
sim_words or sim_seed RE-BASELINES the objective - a change that looked like an improvement \
can actually be worse, and training moves backwards. Change the sample only deliberately.
- max_iterations = ES proposals per run; patience = stop early after this many non-improving \
proposals; grid_search/grid_offsets = coarse sweep around the current weights BEFORE the ES. \
A grid costs len(grid_offsets)**3 exact evaluations (8 offsets = 512 evaluations!), so a long \
offset list can burn the entire timeout before the ES even starts. Keep it short (3-5 values).
- max_guesses = game length limit used by the simulation.
- TIME IS A COST: each iteration runs ONE simulation with a hard timeout ({run_timeout}); a \
killed run wastes the whole iteration. The MEASURED cost of your last proposal (wall-clock, \
per word, per ES proposal) is shown to you every iteration - if it ate the budget, make the \
next one cheaper: smaller sim_words, lower max_iterations / patience, shorter grid_offsets.

## Stop rule (the whole program ENDS when)
A simulation with max_guesses <= 6 produces 0 games that needed {stop_operand} max_guesses \
guesses{stop_note} - i.e. {stop_plain}. The orchestrator confirms it on the full {total_words}-word list; \
sample-only wins do not count.

## AGENT_STRATEGY.md
Keep it structured with the sections: ## Learnings, ## Current hypothesis, ## Plan for next \
iteration. You receive your previous version every iteration; rewrite the full file each time.

## Reply format (strict)
Optional short reasoning first (a <think> block is fine; it is archived, never parsed), then:
```parameters
<complete new parameters.conf content>
```
```strategy
<complete new AGENT_STRATEGY.md content>
```
No file content outside those two blocks. Comments in parameters.conf are normalized by the \
orchestrator, so do not rely on them to carry information.
"""

STOP_STRICT = {
    "operand": ">=",
    "note": " (every word solved in FEWER than max_guesses guesses)",
    "plain": "every word of the list is solved strictly faster than the limit",
}
STOP_LOOSE = {
    "operand": ">",
    "note": " (no failed games; solving in exactly max_guesses is fine)",
    "plain": "no game fails (needs more than max_guesses guesses)",
}


def build_system_prompt(total_words: int, run_timeout: int, loose_cap: bool) -> str:
    rule = STOP_LOOSE if loose_cap else STOP_STRICT
    return SYSTEM_TEMPLATE.format(
        total_words=total_words,
        run_timeout=fmt_duration(run_timeout),
        stop_operand=rule["operand"],
        stop_note=rule["note"],
        stop_plain=rule["plain"],
    )


def build_history_table(history: list[dict], max_rows: int) -> str:
    if not history:
        return "(no runs yet)"
    rows = history[-max_rows:]
    header = "iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note"

    def cell(value: object, width: int) -> str:
        return ("?" if value is None else str(value)).rjust(width)

    lines = [header]
    for row in rows:
        metrics = row.get("metrics") or {}
        average = metrics.get("average")
        lines.append(
            f"{cell(row.get('iteration'), 4)} | "
            f"{'?' if average is None else f'{average:5.3f}'} | "
            f"{str(metrics.get('worst_word', '?')):<16} | "
            f"{cell(metrics.get('games_at_or_over_cap'), 5)} | "
            f"{cell(metrics.get('max_guesses'), 3)} | "
            f"{cell(row.get('sim_words_effective'), 9)} | "
            f"{cell(row.get('exit_code'), 4)} | "
            f"{fmt_duration(row.get('elapsed_seconds') or 0):>7} | "
            f"{row.get('note', '')}"
        )
    return "\n".join(lines)


def build_user_message(
    iteration: int,
    max_iterations: int,
    cumulative_seconds: float,
    last_metrics: dict | None,
    history: list[dict],
    log_tail: str,
    conf_text: str,
    strategy_text: str,
    notices: list[str],
    max_rows: int,
    tail_lines: int,
) -> str:
    metrics_block = "(this is iteration 1: nothing has run yet)" if last_metrics is None else json.dumps(last_metrics, indent=2)
    notices_block = "\n".join(f"- {notice}" for notice in notices) if notices else "- none"
    tail_block = "\n".join(log_tail.splitlines()[-tail_lines:]) if log_tail.strip() else "(no training_log.csv yet)"

    # Measured compute cost of the last simulation (explicit time cost for Qwen).
    cost_block = "(no simulation has run yet)"
    if history:
        last_row = history[-1]
        last_elapsed = float(last_row.get("elapsed_seconds") or 0)
        cost_metrics = last_row.get("metrics") or {}
        cost_words = cost_metrics.get("words_evaluated") or 0
        cost_proposals = cost_metrics.get("iterations_run") or 0
        if last_elapsed > 0:
            cost_lines = [f"- last simulation: {fmt_duration(last_elapsed)} wall-clock"]
            if cost_words:
                cost_lines.append(f"- measured cost: {last_elapsed / cost_words * 1000:.1f} ms per word evaluated ({cost_words} words)")
            if cost_proposals:
                cost_lines.append(f"- measured cost: {last_elapsed / cost_proposals:.2f} s per ES proposal ({cost_proposals} proposals)")
            cost_lines.append("- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts")
            cost_block = "\n".join(cost_lines)

    return f"""## Iteration {iteration} of at most {max_iterations}
Cumulative training time so far: {fmt_duration(cumulative_seconds)}.

### Metrics of the last simulation (weights currently in pesos.csv)
{metrics_block}

### Measured compute cost of the last simulation
{cost_block}

### Run history (oldest first)
{build_history_table(history, max_rows)}

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
{tail_block}
```

### Current parameters.conf (values the last run used)
```parameters
{conf_text.strip()}
```

### Your previous AGENT_STRATEGY.md
{strategy_text.strip() if strategy_text.strip() else "(none yet)"}

### Orchestrator notices
{notices_block}

Decide the next parameters, update your strategy file, and reply in the required format."""


# --------------------------------------------------------------------------- #
# evo_search2 subprocess management
# --------------------------------------------------------------------------- #

def run_evo(
    config_path: Path,
    summary_path: Path,
    *,
    evaluate: bool = False,
    overrides: dict[str, int] | None = None,
    timeout: int,
) -> dict:
    """Run evo_search2.py in its own process group; returns a result dict."""
    cmd = [sys.executable, str(EVO_SCRIPT), "--config", str(config_path), "--summary", str(summary_path)]
    if evaluate:
        cmd.append("--evaluate")
    for key, value in (overrides or {}).items():
        cmd += [f"--{key}", str(value)]
    started = time.perf_counter()
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_DIR), env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,  # POSIX: own group, so a timeout kills the whole pool
        )
    except (AttributeError, OSError):  # pragma: no cover - non-POSIX fallback
        proc = subprocess.Popen(
            cmd, cwd=str(PROJECT_DIR), env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            else:  # pragma: no cover
                proc.kill()
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
    return {
        "cmd": " ".join(cmd),
        "exit_code": proc.returncode,
        "timed_out": timed_out,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "stdout": stdout or "",
        "stderr": stderr or "",
    }


def load_summary(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def stop_decision(summary: dict, loose_cap: bool) -> bool:
    """True when this summary satisfies the stop rule (max_guesses <= 6)."""
    try:
        cap = int(summary.get("max_guesses", 99))
    except (TypeError, ValueError):
        return False
    if cap > 6:
        return False
    if int(summary.get("word_errors", 0) or 0) > 0:
        return False
    key = "over_threshold" if loose_cap else "games_at_or_over_cap"
    return summary.get(key) == 0


def metrics_of(summary: dict) -> dict:
    keys = ("average", "worst_word", "worst_attempts", "over_threshold",
            "games_at_or_over_cap", "max_guesses", "words_evaluated",
            "word_errors", "attempts_histogram", "weights", "iterations_run")
    return {key: summary[key] for key in keys if key in summary}


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #

def preflight(args: argparse.Namespace) -> tuple[dict, str, int]:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    missing = [str(p) for p in (EVO_SCRIPT, PROJECT_DIR / "pesos.csv") if not p.exists()]
    conf_values, conf_text = load_current_conf()
    source = resolve_word_source(conf_values)
    dataset_dir = resolve_dataset_dir(conf_values)
    letters_path = Path(dataset_dir / "statistics" / "letters_position.csv")
    if not letters_path.exists():
        missing.append(str(letters_path))
    if missing:
        raise SystemExit("missing required file(s):\n  - " + "\n  - ".join(missing))
    if not source.exists():
        raise SystemExit(f"word list not found: {source}")

    if not CONF_PATH.exists():
        seeded = {**conf_values, "path_dataset_dir": conf_values.get("path_dataset_dir") or "dataset"}
        CONF_PATH.write_text(conf_schema.render_conf(seeded), encoding="utf-8")
        conf_text = CONF_PATH.read_text(encoding="utf-8")
        conf_values = {**conf_schema.DEFAULTS, **conf_schema.parse_conf_text(conf_text)[0]}
        print(f"created default {CONF_PATH}")
    if not STRATEGY_PATH.exists():
        STRATEGY_PATH.write_text(SEED_STRATEGY, encoding="utf-8")
        print(f"created default {STRATEGY_PATH.name}")

    total_words = count_words(source)
    print(f"word source: {source} ({total_words} words)")

    if not args.dry_run:
        try:
            models = ollama_list_models(args.ollama_url)
        except (urllib.error.URLError, OSError) as error:
            raise SystemExit(
                f"cannot reach Ollama at {args.ollama_url} ({error}).\n"
                "Is it running? Start it with:  ollama serve"
            )
        if not model_available(models, args.model):
            raise SystemExit(
                f"model {args.model!r} not found on this Ollama instance.\n"
                f"Available models: {', '.join(models) or '(none)'}\n"
                "Pass a different one with --model <name>."
            )
        print(f"ollama ok: {args.model}")
    else:
        print("dry-run: skipping Ollama (Qwen keeps previous parameters each iteration)")

    return conf_values, conf_text, total_words


def run_orchestrator(args: argparse.Namespace) -> None:
    global CONF_PATH
    if args.config:
        CONF_PATH = Path(args.config).expanduser().resolve()
    conf_values, conf_text, total_words = preflight(args)
    strategy_text = read_text(STRATEGY_PATH)

    history: list[dict] = []
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            try:
                history.append(json.loads(line))
            except ValueError:
                continue

    loose_note = " --strict-cap (0 games needing >= max_guesses)" if args.strict_cap else ""
    print(f"stop rule:{loose_note or ' Wordle rule (0 games needing MORE than max_guesses, verified on full list)'}")

    system_prompt = build_system_prompt(total_words, args.run_timeout, not args.strict_cap)
    cumulative_seconds = sum(float(row.get("elapsed_seconds") or 0) for row in history)
    start_iteration = len(history) + 1
    last_metrics: dict | None = history[-1].get("metrics") if history else None
    pending_notices: list[str] = []  # notices produced this iteration -> shown to Qwen next iteration
    best_guard: dict | None = None   # regression guard: best comparable run so far (see step 4b)

    for iteration in range(start_iteration, args.max_iterations + 1):
        iter_dir = LOGS_DIR / f"iter_{iteration:03d}_{now_stamp()}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        notices = list(pending_notices)  # what Qwen sees in THIS prompt
        pending_notices = []             # what THIS iteration produces for the next one
        print(f"\n=== iteration {iteration}/{args.max_iterations} -> {iter_dir.name} ===")

        # ---- 1. ask Qwen -----------------------------------------------------
        user_message = build_user_message(
            iteration, args.max_iterations, cumulative_seconds, last_metrics,
            history, read_text(PROJECT_DIR / "training_log.csv"), conf_text,
            strategy_text, notices, args.history_rows, args.log_tail_lines,
        )
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}]
        (iter_dir / "prompt.md").write_text(
            f"<system>\n{system_prompt}\n</system>\n\n<user>\n{user_message}\n</user>\n",
            encoding="utf-8",
        )

        llm_status = "ok"
        repair_user = None
        if args.dry_run:
            response_text, thinking_text = "", "(dry-run: no LLM call)"
        else:
            response_text, thinking_text = "", ""
            for attempt in range(2):
                send_messages = messages if attempt == 0 else messages + [
                    {"role": "assistant", "content": response_text},
                    {"role": "user", "content": repair_user or ""},
                ]
                try:
                    response_text = ollama_chat(
                        args.ollama_url, args.model, send_messages,
                        temperature=args.temperature, num_ctx=args.num_ctx,
                        timeout=args.llm_timeout,
                        think=False if args.no_think else None,
                    )
                except (urllib.error.URLError, OSError, KeyError) as error:
                    llm_status = f"llm_error: {error}"
                    break
                body, thinking_text = split_thinking(response_text)
                params_block, strategy_block, fallback_used = extract_blocks(body)
                if params_block is not None and strategy_block is not None:
                    if fallback_used:
                        pending_notices.append("reply used unlabeled fenced blocks; assumed order parameters->strategy")
                    break
                llm_status = "unparsed"
                repair_user = (
                    "Your reply could not be parsed: I need exactly two fenced blocks, one labeled "
                    "```parameters with the COMPLETE parameters.conf and one labeled ```strategy with "
                    "the COMPLETE AGENT_STRATEGY.md. Please resend both blocks."
                )
            (iter_dir / "response.md").write_text(response_text or f"(error: {llm_status})", encoding="utf-8")
            if thinking_text:
                (iter_dir / "reasoning.md").write_text(thinking_text, encoding="utf-8")

        if args.dry_run:
            new_values = dict(conf_values)
            strategy_new = strategy_text.rstrip() + "\n\n- [dry-run] no-op iteration (parameters unchanged)\n"
            llm_status = "dry-run"
        else:
            body, _ = split_thinking(response_text)
            params_block, strategy_block, _ = extract_blocks(body)
            proposed: dict = {}
            if params_block is not None:
                proposed, parse_errors = conf_schema.parse_conf_text(params_block)
                if parse_errors:
                    pending_notices.append(f"parameters parse errors: {parse_errors}")
            merged = {**conf_values, **proposed}
            violations = conf_schema.validate_values(
                merged, previous=conf_values, total_words=total_words, enforce_locks=True,
            )
            # Belt and braces: locked keys are re-pinned to the current values.
            for key in conf_schema.LOCKED_KEYS:
                merged[key] = conf_values.get(key, conf_schema.DEFAULTS[key])
            if violations:
                llm_status = f"rejected: {'; '.join(violations)}"
                pending_notices.append("your proposal was REJECTED: " + "; ".join(violations))
                new_values = dict(conf_values)
                strategy_new = strategy_text
            else:
                new_values = merged
                strategy_new = strategy_block if strategy_block is not None else strategy_text
                if strategy_block is None:
                    llm_status = "ok (strategy block missing - previous kept)"
                    pending_notices.append("your reply had no strategy block; the previous AGENT_STRATEGY.md was kept")

        params_changed = any(new_values[key] != conf_values.get(key) for key in conf_schema.QWEN_EDITABLE_KEYS)

        # ---- 2. persist the two Qwen-writable files --------------------------
        canonical_conf = conf_schema.render_conf(new_values)
        CONF_PATH.write_text(canonical_conf, encoding="utf-8")
        conf_text = canonical_conf
        STRATEGY_PATH.write_text(strategy_new.rstrip() + "\n", encoding="utf-8")
        strategy_text = STRATEGY_PATH.read_text(encoding="utf-8")
        (iter_dir / "parameters_used.conf").write_text(conf_text, encoding="utf-8")
        (iter_dir / "AGENT_STRATEGY.md").write_text(strategy_text, encoding="utf-8")

        # ---- 3. run the simulation (unless a no-op would repeat the same run) -
        run_skipped = (not params_changed) and last_metrics is not None
        summary: dict | None = None
        run_result: dict = {"exit_code": None, "timed_out": False, "elapsed_seconds": 0, "stdout": "", "stderr": "", "cmd": ""}
        if run_skipped:
            pending_notices.append("run skipped: your parameters are identical to the last run (time is a cost) - change something to trigger a new simulation")
            print("run skipped: parameters unchanged")
        else:
            summary_path = iter_dir / "summary.json"
            print(f"running evo_search2.py (timeout {fmt_duration(args.run_timeout)})...")
            run_result = run_evo(Path(iter_dir / "parameters_used.conf"), summary_path, timeout=args.run_timeout)
            (iter_dir / "stdout.txt").write_text(run_result["stdout"], encoding="utf-8")
            (iter_dir / "stderr.txt").write_text(run_result["stderr"], encoding="utf-8")
            for artifact in ("training_log.csv", "pesos.csv"):
                src = PROJECT_DIR / artifact
                if src.exists():
                    (iter_dir / artifact).write_bytes(src.read_bytes())
            summary = load_summary(summary_path)
            if run_result["timed_out"]:
                pending_notices.append(f"the run hit the {fmt_duration(args.run_timeout)} timeout: shrink sim_words / max_iterations / patience")
            elif run_result["exit_code"] != 0:
                pending_notices.append(f"evo_search2 exited with code {run_result['exit_code']}; see stderr.txt in the iteration log")
            if summary is None:
                pending_notices.append("no summary.json was produced (run crashed or timed out?)")
            else:
                last_metrics = metrics_of(summary)
            cumulative_seconds += run_result["elapsed_seconds"]

        # ---- 4. stop check + full-list verification ---------------------------
        stop_candidate = bool(summary) and stop_decision(summary, not args.strict_cap)
        verified_stop = False
        verify_summary: dict | None = None
        if stop_candidate:
            cap = int(summary["max_guesses"])
            effective_words = int(summary.get("words_evaluated", 0) or 0)
            if effective_words >= total_words:
                verified_stop = True
                print(f"STOP: perfect game on the full list ({effective_words} words, max_guesses={cap})")
            else:
                print(f"sample claim ({effective_words} words) - verifying on the full {total_words}-word list...")
                verify_path = iter_dir / "verify_summary.json"
                verify_run = run_evo(
                    Path(iter_dir / "parameters_used.conf"), verify_path,
                    evaluate=True, overrides={"sim-words": 0, "max-guesses": cap},
                    timeout=args.verify_timeout,
                )
                (iter_dir / "verify_stdout.txt").write_text(verify_run["stdout"], encoding="utf-8")
                verify_summary = load_summary(verify_path)
                if verify_summary is not None and stop_decision(verify_summary, not args.strict_cap):
                    verified_stop = True
                    print(f"STOP: verified on the full list (max_guesses={cap})")
                else:
                    pending_notices.append(
                        "your success claim FAILED verification on the full list - the sample was too easy; "
                        "keep improving with bigger samples or better parameters"
                    )
                    print("verification failed - continuing")

        # ---- 5. archive -------------------------------------------------------
        metrics_row = last_metrics if run_skipped else (metrics_of(summary) if summary else None)

        # ---- 4b. regression guard: training must not move backwards ----------
        # Within one run, evo_search2 only commits improvements on ITS sample.
        # Across iterations the sample/objective can change, so a run can end
        # worse than an earlier comparable run. Guard: while Qwen keeps the
        # same sample basis (sim_words, sim_seed) and the same max_guesses /
        # fail_penalty, compare runs lexicographically (fewer over-threshold
        # games first, then lower average); if a run ends WORSE than the best
        # comparable run, restore pesos.csv from that best iteration. A changed
        # basis re-baselines the guard (deliberate change by Qwen).
        regression_guard = ""
        guard_ok = (
            metrics_row is not None
            and not run_skipped
            and (metrics_row.get("word_errors") or 0) == 0
            and metrics_row.get("average") is not None
        )
        if guard_ok:
            params_key = (
                new_values.get("sim_words"), new_values.get("sim_seed"),
                new_values.get("max_guesses"), new_values.get("fail_penalty"),
            )
            run_key = (metrics_row.get("over_threshold"), metrics_row.get("average"))
            if best_guard is None or best_guard["params_key"] != params_key:
                best_guard = {"params_key": params_key, "key": run_key,
                              "iteration": iteration, "dir": iter_dir}
            elif run_key < best_guard["key"]:
                best_guard = {"params_key": params_key, "key": run_key,
                              "iteration": iteration, "dir": iter_dir}
            elif run_key > best_guard["key"]:
                best_pesos = best_guard["dir"] / "pesos.csv"
                if best_pesos.exists():
                    (PROJECT_DIR / "pesos.csv").write_bytes(best_pesos.read_bytes())
                    regression_guard = (
                        f"run ended worse than iteration {best_guard['iteration']} on the same sample; "
                        f"pesos.csv restored from it (no backwards step)"
                    )
                    pending_notices.append(
                        "your proposal made the result WORSE than the best run on the same sample; "
                        f"pesos.csv was restored from iteration {best_guard['iteration']} - "
                        "training cannot move backwards. Try a different direction."
                    )
                    print(regression_guard)

        history_row = {
            "iteration": iteration,
            "timestamp": now_stamp(),
            "llm_status": llm_status,
            "params_changed": params_changed,
            "run_skipped": run_skipped,
            "exit_code": run_result["exit_code"],
            "timed_out": run_result["timed_out"],
            "elapsed_seconds": run_result["elapsed_seconds"],
            "sim_words_effective": (metrics_row or {}).get("words_evaluated"),
            "metrics": metrics_row,
            "stop_candidate": stop_candidate,
            "verified_stop": verified_stop,
            "regression_guard": regression_guard,
            "note": "; ".join(pending_notices)[:300],
        }
        with HISTORY_PATH.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(history_row) + "\n")
        history.append(history_row)
        (iter_dir / "metrics.json").write_text(json.dumps(history_row, indent=2), encoding="utf-8")
        print(f"iter {iteration}: exit={run_result['exit_code']} elapsed={fmt_duration(run_result['elapsed_seconds'])} "
              f"avg={(metrics_row or {}).get('average', float('nan')):.3f} "
              f">=cap={(metrics_row or {}).get('games_at_or_over_cap', '?')} "
              f"cap={(metrics_row or {}).get('max_guesses', '?')}")

        if verified_stop:
            winner = iter_dir
            winner_summary = verify_summary or summary
            write_final_report(args, iteration, winner, winner_summary or {}, history, cumulative_seconds, total_words)
            print(f"\nPERFECT GAME REACHED - report: {FINAL_REPORT_PATH}")
            return

    print(f"\nfinished {args.max_iterations} iterations without reaching the stop rule.")
    print(f"history: {HISTORY_PATH}")
    print(f"logs:    {LOGS_DIR}")


def write_final_report(
    args: argparse.Namespace,
    iteration: int,
    winner_dir: Path,
    summary: dict,
    history: list[dict],
    cumulative_seconds: float,
    total_words: int,
) -> None:
    rule = ("0 games needing >= max_guesses (strict)" if args.strict_cap
            else "0 games needing MORE than max_guesses (Wordle rule)")
    lines = [
        "# FINAL_REPORT - perfect game reached",
        "",
        f"- Model: {args.model}" + (" (dry-run)" if args.dry_run else ""),
        f"- Winning iteration: {iteration} ({winner_dir.name})",
        f"- Stop rule: {rule}, with max_guesses = {summary.get('max_guesses')}",
        f"- Words evaluated: {summary.get('words_evaluated')} / {total_words} (full list verified)",
        f"- Average guesses: {summary.get('average')}",
        f"- Worst word: {summary.get('worst_word')} ({summary.get('worst_attempts')} attempts)",
        f"- Attempts histogram: {json.dumps(summary.get('attempts_histogram', {}))}",
        f"- Final weights (pesos.csv): {summary.get('weights')}",
        f"- Total training time: {fmt_duration(cumulative_seconds)} over {len(history)} iterations",
        "",
        "## Attempts histogram per iteration (see logs/ for everything else)",
        "",
    ]
    lines += [f"- iter {row.get('iteration')}: avg={((row.get('metrics') or {}).get('average'))} "
              f"cap={(row.get('metrics') or {}).get('max_guesses')} "
              f">=cap={(row.get('metrics') or {}).get('games_at_or_over_cap')} "
              f"note={row.get('note', '')}" for row in history]
    lines += ["", "## Winning parameters.conf", "", "```", read_text(winner_dir / "parameters_used.conf").rstrip(), "```", ""]
    FINAL_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


SEED_STRATEGY = """\
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- (empty - no iteration run yet)

## Current hypothesis
- Start from the current pesos.csv and a small sim_words sample to measure quickly.

## Plan for next iteration
- Read the metrics, then adjust one or two parameters at a time.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None, help="parameters.conf to manage (default: qwen_training/parameters.conf)")
    parser.add_argument("--model", default="qwen3.5-9b", help="Ollama model tag (default: qwen3.5-9b)")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--max-iterations", type=int, default=500, help="maximum Qwen iterations (default: 25)")
    parser.add_argument("--run-timeout", type=int, default=7200, help="per-simulation timeout in seconds (default: 7200)")
    parser.add_argument("--verify-timeout", type=int, default=7200, help="full-list verification timeout in seconds")
    parser.add_argument("--llm-timeout", type=int, default=600, help="per-LLM-call timeout in seconds (default: 600)")
    parser.add_argument("--temperature", type=float, default=0.4, help="LLM temperature (default: 0.4)")
    parser.add_argument("--num-ctx", type=int, default=8192, help="LLM context window (default: 8192)")
    parser.add_argument("--no-think", action="store_true", help="ask the model to skip its <think> phase")
    parser.add_argument("--dry-run", action="store_true", help="skip Ollama; exercises the pipeline with unchanged parameters")
    parser.add_argument("--strict-cap", action="store_true",
                        help="require 0 games needing >= max_guesses. Default is the Wordle rule: "
                             "0 games needing MORE than max_guesses - solving ON the last guess "
                             "counts as solved")
    parser.add_argument("--history-rows", type=int, default=14, help="history rows shown to Qwen each iteration")
    parser.add_argument("--log-tail-lines", type=int, default=40, help="training_log.csv lines shown to Qwen each iteration")
    args = parser.parse_args()
    try:
        run_orchestrator(args)
    except KeyboardInterrupt:
        print("\ninterrupted - progress is kept in history.jsonl and qwen_training/logs/")


if __name__ == "__main__":
    main()
