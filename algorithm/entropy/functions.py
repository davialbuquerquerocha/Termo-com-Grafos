from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import atexit
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
from time import perf_counter
from typing import Callable, Generator

import numpy as np

from algorithm.partition import functions as partition_functions

EXHAUSTIVE_LIMIT = 30
BUDGET = 200_000
FACTOR = 4
MIN_K = 5
ENTROPY_MARGIN = 1.0
RANKING_CHUNK_SIZE = 256
SEARCH_ALGORITHM_VERSION = 3
MEMO_MEMORY_LIMIT = 20_000
MEMO_COMMIT_INTERVAL = 1_000
MEMO_BUSY_TIMEOUT_SECONDS = 300
_BEST_MOVE_CACHE: OrderedDict[
    tuple[str, int, int, int, int, int, float, int, bytes],
    tuple[int, float],
] = OrderedDict()
_BEST_MOVE_CACHE_CONFIG: tuple[int, int, int, int, float, int] | None = None
_MEMO_CONNECTION: sqlite3.Connection | None = None
_MEMO_PATH: Path | None = None
_MEMO_WORD_KEY: str | None = None
_MEMO_CONFIG_KEY: str | None = None
_MEMO_PENDING_WRITES = 0
_PROFILE: "SearchProfile | None" = None

_SearchContext = tuple[
    list[str],
    dict[str, int],
    partition_functions.FeedbackMatrix,
    str,
]


@dataclass
class SearchProfile:
    worker_processes: int = 1
    states_computed: int = 0
    memo_hits: int = 0
    ranking_calls: int = 0
    ranking_seconds: float = 0.0
    guess_evaluations: int = 0
    evaluation_seconds: float = 0.0
    memo_reads: int = 0
    memo_writes: int = 0


@contextmanager
def profile_search() -> Generator[SearchProfile, None, None]:
    """Collect cumulative search timings and operation counts."""
    global _PROFILE
    if _PROFILE is not None:
        raise RuntimeError("Search profiling is already active.")
    profile = SearchProfile()
    _PROFILE = profile
    try:
        yield profile
    finally:
        _PROFILE = None


def _search_config_key() -> tuple[int, int, int, int, float, int]:
    return (
        EXHAUSTIVE_LIMIT,
        BUDGET,
        FACTOR,
        MIN_K,
        ENTROPY_MARGIN,
        SEARCH_ALGORITHM_VERSION,
    )


def _discard_stale_search_memos() -> None:
    global _BEST_MOVE_CACHE_CONFIG
    active_config = _search_config_key()
    if _BEST_MOVE_CACHE_CONFIG == active_config:
        return

    stale_keys = [
        key
        for key in _BEST_MOVE_CACHE
        if key[2:8] != active_config
    ]
    for key in stale_keys:
        del _BEST_MOVE_CACHE[key]
    _BEST_MOVE_CACHE_CONFIG = active_config


def _serialized_config_key() -> str:
    return json.dumps(_search_config_key(), separators=(",", ":"))


def configure_memo_store(path: Path, word_key: str) -> None:
    """Open the persistent memo database for this word list and search config."""
    global _MEMO_CONNECTION, _MEMO_PATH, _MEMO_WORD_KEY
    global _MEMO_CONFIG_KEY, _MEMO_PENDING_WRITES, _BEST_MOVE_CACHE_CONFIG
    config_key = _serialized_config_key()
    resolved_path = path.resolve()
    if (
        _MEMO_CONNECTION is not None
        and _MEMO_PATH == resolved_path
        and _MEMO_WORD_KEY == word_key
        and _MEMO_CONFIG_KEY == config_key
    ):
        return

    close_memo_store()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        resolved_path,
        timeout=MEMO_BUSY_TIMEOUT_SECONDS,
    )
    connection.execute(
        f"PRAGMA busy_timeout={MEMO_BUSY_TIMEOUT_SECONDS * 1_000}"
    )
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS memo_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS best_moves (
            word_key TEXT NOT NULL,
            depth INTEGER NOT NULL,
            config_key TEXT NOT NULL,
            candidate_indices BLOB NOT NULL,
            guess_index INTEGER NOT NULL,
            expected_cost REAL NOT NULL,
            PRIMARY KEY (
                word_key,
                depth,
                config_key,
                candidate_indices
            )
        );
        CREATE TABLE IF NOT EXISTS evaluation_results (
            word_key TEXT NOT NULL,
            config_key TEXT NOT NULL,
            evaluation_key TEXT NOT NULL,
            strategy TEXT NOT NULL,
            answer TEXT NOT NULL,
            attempts INTEGER NOT NULL,
            PRIMARY KEY (
                word_key,
                config_key,
                evaluation_key,
                strategy,
                answer
            )
        );
        """
    )
    metadata = dict(connection.execute("SELECT key, value FROM memo_metadata"))
    if (
        metadata.get("active_config") != config_key
        or metadata.get("active_word_key") != word_key
    ):
        connection.execute(
            "DELETE FROM best_moves WHERE config_key != ? OR word_key != ?",
            (config_key, word_key),
        )
        connection.execute(
            "DELETE FROM evaluation_results WHERE config_key != ? OR word_key != ?",
            (config_key, word_key),
        )
        connection.executemany(
            """
            INSERT INTO memo_metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (
                ("active_config", config_key),
                ("active_word_key", word_key),
            ),
        )
    connection.commit()

    _MEMO_CONNECTION = connection
    _MEMO_PATH = resolved_path
    _MEMO_WORD_KEY = word_key
    _MEMO_CONFIG_KEY = config_key
    _MEMO_PENDING_WRITES = 0
    _BEST_MOVE_CACHE.clear()
    _BEST_MOVE_CACHE_CONFIG = _search_config_key()


def close_memo_store() -> None:
    """Commit pending memo writes and close the persistent store."""
    global _MEMO_CONNECTION, _MEMO_PATH, _MEMO_WORD_KEY
    global _MEMO_CONFIG_KEY, _MEMO_PENDING_WRITES
    if _MEMO_CONNECTION is not None:
        _MEMO_CONNECTION.commit()
        _MEMO_CONNECTION.close()
    _MEMO_CONNECTION = None
    _MEMO_PATH = None
    _MEMO_WORD_KEY = None
    _MEMO_CONFIG_KEY = None
    _MEMO_PENDING_WRITES = 0


atexit.register(close_memo_store)


def _require_memo_connection() -> sqlite3.Connection:
    if _MEMO_CONNECTION is None:
        raise RuntimeError("The persistent search memo has not been configured.")
    return _MEMO_CONNECTION


def _memo_get(
    state_key: tuple[str, int, int, int, int, int, float, int, bytes],
) -> tuple[int, float] | None:
    global _MEMO_PENDING_WRITES
    cached = _BEST_MOVE_CACHE.get(state_key)
    if cached is not None:
        _BEST_MOVE_CACHE.move_to_end(state_key)
        if _PROFILE is not None:
            _PROFILE.memo_hits += 1
        return cached

    if _PROFILE is not None:
        _PROFILE.memo_reads += 1
    connection = _require_memo_connection()
    word_key, depth, *rest = state_key
    config_key = _serialized_config_key()
    candidate_indices = rest[-1]
    row = connection.execute(
        """
        SELECT guess_index, expected_cost
        FROM best_moves
        WHERE word_key = ? AND depth = ? AND config_key = ?
          AND candidate_indices = ?
        """,
        (word_key, depth, config_key, candidate_indices),
    ).fetchone()
    if row is None:
        return None

    result = int(row[0]), float(row[1])
    if result[0] < 0 or not np.isfinite(result[1]) or result[1] <= 0:
        raise RuntimeError("The persisted search memo contains an invalid result.")
    _remember_state(state_key, result)
    if _PROFILE is not None:
        _PROFILE.memo_hits += 1
    return result


def _remember_state(
    state_key: tuple[str, int, int, int, int, int, float, int, bytes],
    result: tuple[int, float],
) -> None:
    _BEST_MOVE_CACHE[state_key] = result
    _BEST_MOVE_CACHE.move_to_end(state_key)
    while len(_BEST_MOVE_CACHE) > MEMO_MEMORY_LIMIT:
        _BEST_MOVE_CACHE.popitem(last=False)


def _memo_put(
    state_key: tuple[str, int, int, int, int, int, float, int, bytes],
    result: tuple[int, float],
) -> None:
    global _MEMO_PENDING_WRITES
    _remember_state(state_key, result)
    word_key, depth, *rest = state_key
    config_key = _serialized_config_key()
    candidate_indices = rest[-1]
    connection = _require_memo_connection()
    connection.execute(
        """
        INSERT INTO best_moves (
            word_key,
            depth,
            config_key,
            candidate_indices,
            guess_index,
            expected_cost
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (
            word_key,
            depth,
            config_key,
            candidate_indices
        ) DO UPDATE SET
            guess_index = excluded.guess_index,
            expected_cost = excluded.expected_cost
        """,
        (word_key, depth, config_key, candidate_indices, *result),
    )
    _MEMO_PENDING_WRITES += 1
    if _PROFILE is not None:
        _PROFILE.memo_writes += 1
    if _MEMO_PENDING_WRITES >= MEMO_COMMIT_INTERVAL:
        connection.commit()
        _MEMO_PENDING_WRITES = 0


def memo_store_stats() -> dict[str, int | str | None]:
    """Return persistent and in-memory memo usage for diagnostics."""
    database_rows = 0
    if _MEMO_CONNECTION is not None:
        row = _MEMO_CONNECTION.execute(
            "SELECT COUNT(*) FROM best_moves"
        ).fetchone()
        database_rows = int(row[0]) if row is not None else 0
    return {
        "path": str(_MEMO_PATH) if _MEMO_PATH is not None else None,
        "database_rows": database_rows,
        "memory_entries": len(_BEST_MOVE_CACHE),
        "memory_key_bytes": sum(len(key[-1]) for key in _BEST_MOVE_CACHE),
    }


def evaluation_scope_key(answers: list[str]) -> str:
    digest = hashlib.sha256()
    for answer in answers:
        digest.update(answer.encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def load_evaluation_results(
    strategy: str,
    evaluation_key: str,
) -> dict[str, int]:
    rows = _require_memo_connection().execute(
        """
        SELECT answer, attempts
        FROM evaluation_results
        WHERE word_key = ? AND config_key = ?
          AND evaluation_key = ? AND strategy = ?
        """,
        (_MEMO_WORD_KEY, _serialized_config_key(), evaluation_key, strategy),
    )
    return {str(answer): int(attempts) for answer, attempts in rows}


def save_evaluation_results(
    strategy: str,
    evaluation_key: str,
    attempts_by_answer: dict[str, int],
) -> None:
    connection = _require_memo_connection()
    connection.executemany(
        """
        INSERT INTO evaluation_results (
            word_key,
            config_key,
            evaluation_key,
            strategy,
            answer,
            attempts
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (
            word_key,
            config_key,
            evaluation_key,
            strategy,
            answer
        ) DO UPDATE SET attempts = excluded.attempts
        """,
        (
            (
                _MEMO_WORD_KEY,
                _serialized_config_key(),
                evaluation_key,
                strategy,
                answer,
                attempts,
            )
            for answer, attempts in attempts_by_answer.items()
        ),
    )
    connection.commit()


def clear_evaluation_results(strategy: str, evaluation_key: str) -> None:
    _require_memo_connection().execute(
        """
        DELETE FROM evaluation_results
        WHERE word_key = ? AND config_key = ?
          AND evaluation_key = ? AND strategy = ?
        """,
        (_MEMO_WORD_KEY, _serialized_config_key(), evaluation_key, strategy),
    )
    _require_memo_connection().commit()


def search_profile_summary(profile: SearchProfile) -> dict[str, int | float | str | None]:
    return {
        "worker_processes": profile.worker_processes,
        "states_computed": profile.states_computed,
        "memo_hits": profile.memo_hits,
        "ranking_calls": profile.ranking_calls,
        "ranking_seconds": profile.ranking_seconds,
        "guess_evaluations": profile.guess_evaluations,
        "evaluation_seconds": profile.evaluation_seconds,
        "memo_reads": profile.memo_reads,
        "memo_writes": profile.memo_writes,
        **memo_store_stats(),
    }


def parse_feedback(text: str) -> int:
    """Convert a five-letter P/A/V feedback string to its base-3 code."""
    normalized_text = text.strip().upper()
    if len(normalized_text) != 5:
        raise ValueError("Feedback must contain exactly five characters.")

    mark_values = {"P": 0, "A": 1, "V": 2}
    invalid_marks = set(normalized_text) - mark_values.keys()
    if invalid_marks:
        raise ValueError(
            "Feedback may contain only P (black), A (yellow), and V (green)."
        )

    return sum(
        mark_values[mark] * (3**position)
        for position, mark in enumerate(normalized_text)
    )


@lru_cache(maxsize=8)
def _guess_count(path: str) -> int:
    with open(path, encoding="utf-8") as file:
        return len(
            {
                word.strip().upper()
                for word in file
                if word.strip()
            }
        )


def k_by_size(n: int, depth: int = 0) -> int:
    """Choose how many guesses to evaluate for a candidate state of size n."""
    if n <= 0:
        raise ValueError("n must be greater than zero.")
    if depth < 0:
        raise ValueError("depth must be non-negative.")
    if n <= 2:
        return 1

    guess_count = _guess_count(str(partition_functions.DATASET_PATH))
    if n <= EXHAUSTIVE_LIMIT:
        return guess_count

    budgeted_k = BUDGET // (n * FACTOR**depth)
    return min(guess_count, max(MIN_K, budgeted_k))


def _rank_state(
    candidates: list[str],
    depth: int,
    context: _SearchContext,
) -> list[int]:
    _, word_indices, matrix, _ = context
    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in candidates),
        dtype=np.intp,
        count=len(candidates),
    )
    vocab_size = _guess_count(str(partition_functions.DATASET_PATH))
    eligible_indices = np.asarray(
        sorted(
            {
                *range(vocab_size),
                *candidate_indices.tolist(),
            }
        ),
        dtype=np.intp,
    )
    entropies = np.empty(len(eligible_indices), dtype=np.float64)
    candidate_count = len(candidates)
    for start in range(0, len(eligible_indices), RANKING_CHUNK_SIZE):
        stop = min(start + RANKING_CHUNK_SIZE, len(eligible_indices))
        guess_indices = eligible_indices[start:stop]
        feedback_codes = matrix[
            guess_indices[:, None],
            candidate_indices,
        ].astype(np.int32)
        feedback_offsets = (
            np.arange(len(guess_indices), dtype=np.int32)[:, None]
            * partition_functions._FEEDBACK_PATTERN_COUNT
        )
        counts = np.bincount(
            (feedback_codes + feedback_offsets).ravel(),
            minlength=(
                len(guess_indices)
                * partition_functions._FEEDBACK_PATTERN_COUNT
            ),
        ).reshape(
            len(guess_indices),
            partition_functions._FEEDBACK_PATTERN_COUNT,
        )
        log_counts = np.zeros_like(counts, dtype=np.float64)
        nonzero_counts = counts > 0
        log_counts[nonzero_counts] = np.log2(counts[nonzero_counts])
        entropies[start:stop] = (
            np.log2(candidate_count)
            - np.sum(counts * log_counts, axis=1) / candidate_count
        )

    order = np.argsort(-entropies, kind="stable")
    if len(candidates) > EXHAUSTIVE_LIMIT and len(order):
        order = order[
            entropies[order] >= entropies[order[0]] - ENTROPY_MARGIN
        ]
    guess_limit = (
        len(eligible_indices)
        if len(candidates) <= EXHAUSTIVE_LIMIT
        else k_by_size(len(candidates), depth)
    )
    return eligible_indices[order[:guess_limit]].tolist()


def _evaluate_guess(
    guess_index: int,
    candidates: list[str],
    limit: float,
    depth: int,
    context: _SearchContext,
    group_progress_callback: Callable[[], None] | None = None,
) -> float:
    guesses, word_indices, matrix, _ = context
    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in candidates),
        dtype=np.intp,
        count=len(candidates),
    )
    feedback_codes = matrix[word_indices[guesses[guess_index]], candidate_indices]
    groups: dict[int, list[str]] = {}
    for candidate, code in zip(candidates, feedback_codes):
        groups.setdefault(int(code), []).append(candidate)

    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    remaining_groups = [
        group for code, group in groups.items() if code != winning_feedback
    ]
    if any(len(group) == len(candidates) for group in remaining_groups):
        return float("inf")

    expected_cost = 1.0
    for group in sorted(remaining_groups, key=len):
        _, group_cost = _best_move(
            group,
            depth + 1,
            context,
            group_progress_callback=group_progress_callback,
        )
        if group_progress_callback is not None:
            group_progress_callback()
        expected_cost += len(group) * group_cost / len(candidates)
        if expected_cost > limit:
            return float("inf")
    return expected_cost


def _best_move(
    candidates: list[str],
    depth: int,
    context: _SearchContext,
    parallel_evaluator: Callable[
        [list[str], list[int], int, _SearchContext],
        tuple[int, float],
    ] | None = None,
    group_progress_callback: Callable[[], None] | None = None,
) -> tuple[int, float]:
    _, _, _, word_key = context
    if _MEMO_CONNECTION is None:
        raise RuntimeError("The persistent search memo has not been configured.")
    if (
        _MEMO_CONFIG_KEY != _serialized_config_key()
        or _MEMO_WORD_KEY != word_key
    ):
        if _MEMO_PATH is None:
            raise RuntimeError("The persistent search memo path is unavailable.")
        configure_memo_store(_MEMO_PATH, word_key)
    _discard_stale_search_memos()
    _, word_indices, _, _ = context
    candidate_indices = np.fromiter(
        sorted(word_indices[candidate] for candidate in candidates),
        dtype=np.uint32,
        count=len(candidates),
    )
    state_key = (
        word_key,
        depth,
        *_search_config_key(),
        candidate_indices.tobytes(),
    )
    cached = _memo_get(state_key)
    if cached is not None:
        if cached[0] >= len(context[0]):
            raise RuntimeError("The persisted search memo contains an invalid guess index.")
        return cached

    if _PROFILE is not None:
        _PROFILE.states_computed += 1
    if len(candidates) == 1:
        result = word_indices[candidates[0]], 1.0
    elif len(candidates) == 2:
        result = word_indices[candidates[0]], 1.5
    else:
        best_guess = -1
        best_cost = float("inf")
        ranking_started = perf_counter()
        ranked_guesses = _rank_state(candidates, depth, context)
        if _PROFILE is not None:
            _PROFILE.ranking_calls += 1
            _PROFILE.ranking_seconds += perf_counter() - ranking_started
        if parallel_evaluator is not None:
            best_guess, best_cost = parallel_evaluator(
                candidates,
                ranked_guesses,
                depth,
                context,
            )
        else:
            for guess_index in ranked_guesses:
                evaluation_started = perf_counter()
                cost = _evaluate_guess(
                    guess_index,
                    candidates,
                    best_cost,
                    depth,
                    context,
                    group_progress_callback,
                )
                if _PROFILE is not None:
                    _PROFILE.guess_evaluations += 1
                    _PROFILE.evaluation_seconds += perf_counter() - evaluation_started
                if cost < best_cost:
                    best_guess = guess_index
                    best_cost = cost
        if best_guess < 0:
            raise RuntimeError("No guess produced a valid partition.")
        result = best_guess, best_cost

    if not np.isfinite(result[1]):
        raise RuntimeError("A pruned or non-finite search result cannot be memoized.")
    _memo_put(state_key, result)
    return result


def partitioning(guess: str, candidates: list[str]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    normalized_guess = guess.strip().upper()
    normalized_candidates = [candidate.strip().upper() for candidate in candidates]
    words = [normalized_guess, *normalized_candidates]
    feedback_matrix, word_indices, _ = partition_functions._get_feedback_matrix(words)
    for candidate, normalized_candidate in zip(candidates, normalized_candidates):
        feedback = int(feedback_matrix[word_indices[normalized_guess], word_indices[normalized_candidate]])
        groups.setdefault(feedback, []).append(candidate)
    return groups


def entropy(guess: str, candidates: list[str]) -> float:
    normalized_guess = guess.strip().upper()
    normalized_candidates = [candidate.strip().upper() for candidate in candidates]
    words = [normalized_guess, *normalized_candidates]
    feedback_matrix, word_indices, _ = partition_functions._get_feedback_matrix(words)

    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in normalized_candidates),
        dtype=np.intp,
        count=len(normalized_candidates),
    )
    feedback_codes = feedback_matrix[word_indices[normalized_guess], candidate_indices]
    counts = np.bincount(feedback_codes)
    probabilities = counts[counts > 0] / len(candidates)
    return float(-np.sum(probabilities * np.log2(probabilities)))


def ranking_with_context(
    candidates: list[str],
    K: int,
    context: _SearchContext,
) -> list[int]:
    """Rank guesses by entropy and include every candidate guess.

    Indices refer to the accepted-word list, with candidates absent from that
    list appended in their first-seen order.
    """
    if K < 0:
        raise ValueError("K must be non-negative.")
    if not candidates:
        raise ValueError("candidates must not be empty.")

    ranking_started = perf_counter()
    guesses, word_indices, feedback_matrix, _ = context
    normalized_candidates = [candidate.strip().upper() for candidate in candidates]
    for candidate in normalized_candidates:
        if candidate not in word_indices:
            raise ValueError(f"Candidate {candidate!r} is missing from the search context.")
    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in normalized_candidates),
        dtype=np.intp,
        count=len(normalized_candidates),
    )

    entropies = np.empty(len(guesses), dtype=np.float64)
    candidate_count = len(candidates)
    for start in range(0, len(guesses), RANKING_CHUNK_SIZE):
        stop = min(start + RANKING_CHUNK_SIZE, len(guesses))
        guess_row_indices = np.arange(start, stop, dtype=np.intp)
        feedback_codes = feedback_matrix[
            guess_row_indices[:, None], candidate_indices
        ].astype(np.int32)
        feedback_offsets = (
            np.arange(len(guess_row_indices), dtype=np.int32)[:, None]
            * partition_functions._FEEDBACK_PATTERN_COUNT
        )
        counts = np.bincount(
            (feedback_codes + feedback_offsets).ravel(),
            minlength=(
                len(guess_row_indices)
                * partition_functions._FEEDBACK_PATTERN_COUNT
            ),
        ).reshape(
            len(guess_row_indices),
            partition_functions._FEEDBACK_PATTERN_COUNT,
        )
        log_counts = np.zeros_like(counts, dtype=np.float64)
        nonzero_counts = counts > 0
        log_counts[nonzero_counts] = np.log2(counts[nonzero_counts])
        entropies[start:stop] = (
            np.log2(candidate_count)
            - np.sum(counts * log_counts, axis=1) / candidate_count
        )

    ranked_indices = np.argsort(-entropies, kind="stable")[:K].tolist()
    candidate_guess_indices = [
        word_indices[candidate] for candidate in normalized_candidates
    ]
    result = list(dict.fromkeys([*ranked_indices, *candidate_guess_indices]))
    if _PROFILE is not None:
        _PROFILE.ranking_calls += 1
        _PROFILE.ranking_seconds += perf_counter() - ranking_started
    return result


def ranking(candidates: list[str], K: int) -> list[int]:
    """Rank guesses by entropy, building the word-list context if needed."""
    normalized_candidates = [candidate.strip().upper() for candidate in candidates]
    with partition_functions.DATASET_PATH.open(encoding="utf-8") as file:
        guesses = list(
            dict.fromkeys(word.strip().upper() for word in file if word.strip())
        )
    for candidate in normalized_candidates:
        if candidate not in guesses:
            guesses.append(candidate)
    matrix, indices, word_key = partition_functions._get_feedback_matrix(guesses)
    return ranking_with_context(
        normalized_candidates,
        K,
        (guesses, indices, matrix, word_key),
    )
