"""Schema + validator for qwen_training/parameters.conf.

Single source of truth shared by run_qwen_training.py (which parses, validates
and re-renders the file Qwen writes) and evo_search2.py (which reads it).

NOTE: this module was NOT part of the uploaded files - it was rebuilt to the
exact contract both scripts use (DEFAULTS mirror evo_search2._FALLBACK_DEFAULTS,
API: DEFAULTS / LOCKED_KEYS / QWEN_EDITABLE_KEYS / parse_conf_text /
render_conf / validate_values). If you still have your original conf_schema.py,
diff it against this one before trusting it.
"""

from __future__ import annotations

# Canonical key order used by render_conf().
_KEY_ORDER = [
    "max_iterations", "patience", "step_fraction", "rule_window",
    "rule_target", "rule_factor", "min_step_fraction",
    "grid_search", "grid_offsets",
    "seed", "max_guesses", "fail_penalty",
    "parallel_workers",
    "sim_words", "sim_seed",
    "path_dataset_dir", "path_termo_words", "path_accepted_words",
]

_INT_KEYS = {
    "max_iterations", "patience", "rule_window", "parallel_workers",
    "sim_words", "sim_seed", "seed", "max_guesses",
}
_FLOAT_KEYS = {
    "step_fraction", "rule_target", "rule_factor",
    "min_step_fraction", "fail_penalty",
}
_PATH_KEYS = ("path_dataset_dir", "path_termo_words", "path_accepted_words")

DEFAULTS: dict = {
    "max_iterations": 2000,
    "patience": 200,
    "step_fraction": 1.0,
    "rule_window": 20,
    "rule_target": 0.2,
    "rule_factor": 1.5,
    "min_step_fraction": 0.001,
    "grid_search": True,
    "grid_offsets": [-4, -1, 1, 4],
    "seed": 7,
    "max_guesses": 6,
    "fail_penalty": 2.0,
    "sim_words": 0,
    "sim_seed": 7,
    "parallel_workers": 17,
    "path_dataset_dir": "",
    "path_termo_words": "",
    "path_accepted_words": "",
}

LOCKED_KEYS = ["parallel_workers", "path_dataset_dir", "path_termo_words", "path_accepted_words"]
QWEN_EDITABLE_KEYS = [key for key in _KEY_ORDER if key not in LOCKED_KEYS]

_BOOL_TRUE = {"true", "1", "yes", "on"}
_BOOL_FALSE = {"false", "0", "no", "off"}


def _coerce(key: str, value: str):
    if key == "grid_search":
        low = value.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise ValueError("grid_search must be true or false")
    if key == "grid_offsets":
        inner = value.strip().strip("[]").strip()
        if not inner:
            return []
        return [int(part.strip()) for part in inner.split(",") if part.strip()]
    if key in _PATH_KEYS:
        return value.strip().strip("'\"")
    if key in _INT_KEYS:
        return int(value)
    if key in _FLOAT_KEYS:
        return float(value)
    raise ValueError(f"unknown key {key!r}")


def parse_conf_text(text: str) -> tuple[dict, list[str]]:
    """Parse parameters.conf content -> (values, errors).

    Ignores blank lines and # comments. Unknown keys and bad values are
    reported as errors; the caller decides what to keep.
    """
    values: dict = {}
    errors: list[str] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            errors.append(f"line {lineno}: expected 'key = value'")
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key not in DEFAULTS:
            errors.append(f"line {lineno}: unknown key {key!r}")
            continue
        try:
            values[key] = _coerce(key, value)
        except ValueError as error:
            errors.append(f"line {lineno}: {key}: {error}")
    return values, errors


def _format_value(key: str, value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def render_conf(values: dict) -> str:
    """Canonical parameters.conf text (same layout as the original file)."""
    merged = {**DEFAULTS, **values}
    lines = [
        "# =====================================================================",
        "# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)",
        "# evo_search2.py reads this file on every start.",
        "# Enforced by run_qwen_training.py:",
        "#   * parallel_workers and every path_* key are LOCKED for Qwen",
        "#   * max_guesses must stay <= 6",
        "#   * sim_words = 0 means \"use the whole source word list\"",
        "# =====================================================================",
        "",
    ]
    for key in _KEY_ORDER:
        if key == "parallel_workers":
            lines += ["# LOCKED - Qwen cannot change this (safety: CPU usage)"]
        elif key == "sim_words":
            lines += ["", "# Simulation set: 0 = every word of the source list. Start small!"]
        elif key == "path_dataset_dir":
            lines += ["", "# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)"]
        lines.append(f"{key} = {_format_value(key, merged[key])}")
    return "\n".join(lines) + "\n"


def validate_values(
    values: dict,
    previous: dict | None = None,
    total_words: int | None = None,
    enforce_locks: bool = False,
) -> list[str]:
    """Sanity rules for a (merged) parameter set -> list of violation strings."""
    errors: list[str] = []
    merged = {**DEFAULTS, **values}

    def as_int(name: str):
        value = merged.get(name)
        try:
            return int(value)
        except (TypeError, ValueError):
            errors.append(f"{name} must be an integer (got {value!r})")
            return None

    def as_float(name: str):
        value = merged.get(name)
        try:
            return float(value)
        except (TypeError, ValueError):
            errors.append(f"{name} must be a number (got {value!r})")
            return None

    max_iterations = as_int("max_iterations")
    if max_iterations is not None and max_iterations < 1:
        errors.append("max_iterations must be >= 1")
    patience = as_int("patience")
    if patience is not None and patience < 1:
        errors.append("patience must be >= 1")
    rule_window = as_int("rule_window")
    if rule_window is not None and rule_window < 1:
        errors.append("rule_window must be >= 1")
    parallel_workers = as_int("parallel_workers")
    if parallel_workers is not None and parallel_workers < 1:
        errors.append("parallel_workers must be >= 1")
    sim_words = as_int("sim_words")
    if sim_words is not None and sim_words < 0:
        errors.append("sim_words must be >= 0 (0 = full word list)")
    if total_words and sim_words is not None and sim_words > total_words:
        errors.append(f"sim_words exceeds the {total_words}-word source list")
    as_int("seed")
    as_int("sim_seed")
    max_guesses = as_int("max_guesses")
    if max_guesses is not None and not 1 <= max_guesses <= 6:
        errors.append("max_guesses must stay <= 6 (Termo rules)")

    as_float("step_fraction")
    step_fraction = as_float("step_fraction")
    if step_fraction is not None and step_fraction <= 0:
        errors.append("step_fraction must be > 0 (it is the initial proposal radius)")
    min_step_fraction = as_float("min_step_fraction")
    if min_step_fraction is not None and min_step_fraction <= 0:
        errors.append("min_step_fraction must be > 0")
    rule_target = as_float("rule_target")
    if rule_target is not None and not 0 < rule_target <= 1:
        errors.append("rule_target must be in (0, 1]")
    rule_factor = as_float("rule_factor")
    if rule_factor is not None and rule_factor <= 1:
        errors.append("rule_factor must be > 1 (it grows/shrinks the step)")
    fail_penalty = as_float("fail_penalty")
    if fail_penalty is not None and fail_penalty < 0:
        errors.append("fail_penalty must be >= 0")

    if not isinstance(merged.get("grid_search"), bool):
        errors.append("grid_search must be true or false")
    grid_offsets = merged.get("grid_offsets")
    if not isinstance(grid_offsets, (list, tuple)) or not grid_offsets:
        errors.append("grid_offsets must be a non-empty list of integers, e.g. [-4, -1, 1, 4]")
    else:
        for offset in grid_offsets:
            if isinstance(offset, bool) or not isinstance(offset, int):
                errors.append("grid_offsets must contain integers only")
                break

    for name in _PATH_KEYS:
        if not isinstance(merged.get(name), str):
            errors.append(f"{name} must be a string")

    if enforce_locks and previous is not None:
        for name in LOCKED_KEYS:
            if merged.get(name) != previous.get(name):
                errors.append(f"{name} is LOCKED for Qwen - copy the current value unchanged")

    return errors
