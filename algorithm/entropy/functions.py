from functools import lru_cache

import numpy as np

from algorithm.partition import functions as partition_functions

EXHAUSTIVE_LIMIT = 30
BUDGET = 200_000
FACTOR = 4
MIN_K = 5
ENTROPY_MARGIN = 1.0
RANKING_CHUNK_SIZE = 256
_BEST_MOVE_CACHE: dict[
    tuple[str, int, int, int, int, int, float, tuple[str, ...]],
    tuple[int, float],
] = {}
_BEST_MOVE_CACHE_CONFIG: tuple[int, int, int, int, float] | None = None

_SearchContext = tuple[
    list[str],
    dict[str, int],
    partition_functions.FeedbackMatrix,
    str,
]


def _search_config_key() -> tuple[int, int, int, int, float]:
    return (
        EXHAUSTIVE_LIMIT,
        BUDGET,
        FACTOR,
        MIN_K,
        ENTROPY_MARGIN,
    )


def _discard_stale_search_memos() -> None:
    global _BEST_MOVE_CACHE_CONFIG
    active_config = _search_config_key()
    if _BEST_MOVE_CACHE_CONFIG == active_config:
        return

    stale_keys = [
        key
        for key in _BEST_MOVE_CACHE
        if key[2:7] != active_config
    ]
    for key in stale_keys:
        del _BEST_MOVE_CACHE[key]
    _BEST_MOVE_CACHE_CONFIG = active_config


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
        _, group_cost = _best_move(group, depth + 1, context)
        expected_cost += len(group) * group_cost / len(candidates)
        if expected_cost > limit:
            return float("inf")
    return expected_cost


def _best_move(
    candidates: list[str],
    depth: int,
    context: _SearchContext,
) -> tuple[int, float]:
    _discard_stale_search_memos()
    _, word_indices, _, word_key = context
    state_key = (
        word_key,
        depth,
        *_search_config_key(),
        tuple(sorted(candidates)),
    )
    cached = _BEST_MOVE_CACHE.get(state_key)
    if cached is not None:
        return cached

    if len(candidates) == 1:
        result = word_indices[candidates[0]], 1.0
    elif len(candidates) == 2:
        result = word_indices[candidates[0]], 1.5
    else:
        best_guess = -1
        best_cost = float("inf")
        for guess_index in _rank_state(candidates, depth, context):
            cost = _evaluate_guess(
                guess_index,
                candidates,
                best_cost,
                depth,
                context,
            )
            if cost < best_cost:
                best_guess = guess_index
                best_cost = cost
        if best_guess < 0:
            raise RuntimeError("No guess produced a valid partition.")
        result = best_guess, best_cost

    _BEST_MOVE_CACHE[state_key] = result
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


def ranking(candidates: list[str], K: int) -> list[int]:
    """Rank guesses by entropy and include every candidate guess.

    Indices refer to the accepted-word list, with candidates absent from that
    list appended in their first-seen order.
    """
    if K < 0:
        raise ValueError("K must be non-negative.")
    if not candidates:
        raise ValueError("candidates must not be empty.")

    with partition_functions.DATASET_PATH.open(encoding="utf-8") as file:
        guesses = list(
            dict.fromkeys(word.strip().upper() for word in file if word.strip())
        )

    normalized_candidates = [candidate.strip().upper() for candidate in candidates]
    guess_indices = {word: index for index, word in enumerate(guesses)}
    for candidate in normalized_candidates:
        if candidate not in guess_indices:
            guess_indices[candidate] = len(guesses)
            guesses.append(candidate)

    feedback_matrix, word_indices, _ = partition_functions._get_feedback_matrix(
        guesses
    )
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
        guess_indices[candidate] for candidate in normalized_candidates
    ]
    return list(dict.fromkeys([*ranked_indices, *candidate_guess_indices]))
