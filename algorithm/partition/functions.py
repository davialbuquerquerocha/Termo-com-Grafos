"""Helpers for feedback matrices and partition-based word selection."""

import hashlib
from pathlib import Path
import random

import numpy as np

from algorithm import functions as common
from algorithm import termo_implementation as t

Feedback = common.Feedback
VOWELS = frozenset("AEIOU")
DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "dataset"
    / "termo_palavras_aceitas.txt"
)

FeedbackMatrix = np.ndarray

_FEEDBACK_MATRIX_CACHE: dict[str, FeedbackMatrix] = {}
_WORD_INDEX_CACHE: dict[str, dict[str, int]] = {}
_PARTITION_GUESS_CACHE: dict[tuple[str, bytes, tuple[int, ...]], int] = {}
_FIRST_GUESS_CACHE: dict[str, int] = {}
_BOUNDED_GUESS_OVERRIDES: dict[tuple[str, bytes], int] = {}
_MATRIX_VALIDATED: set[str] = set()
_FEEDBACK_PATTERN_COUNT = 3**5
_MATRIX_CHUNK_SIZE = 256

def _words_key(word_list: list[str]) -> str:
    digest = hashlib.sha256()
    for word in word_list:
        digest.update(word.strip().upper().encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _feedback_code(feedback: common.Feedback) -> int:
    marks = [0] * 5
    for _, position in feedback[1]:
        marks[position - 1] = 1
    for _, position in feedback[2]:
        marks[position - 1] = 2
    return sum(mark * (3**position) for position, mark in enumerate(marks))


def _candidate_state_key(possible_indices: list[int]) -> bytes:
    return hashlib.sha256(
        np.asarray(possible_indices, dtype=np.uint32).tobytes()
    ).digest()


def install_bounded_guess_overrides(
    overrides: dict[tuple[str, bytes], int],
) -> None:
    """Install per-word-list fallback guesses prepared by the batch runner."""
    _BOUNDED_GUESS_OVERRIDES.clear()
    _BOUNDED_GUESS_OVERRIDES.update(overrides)


def _partition_children(
    possible_indices: tuple[int, ...],
    guess_index: int,
    matrix: FeedbackMatrix,
) -> list[tuple[int, ...]]:
    feedbacks = matrix[guess_index, np.asarray(possible_indices, dtype=np.intp)]
    groups: dict[int, list[int]] = {}
    for answer_index, feedback_code in zip(possible_indices, feedbacks):
        groups.setdefault(int(feedback_code), []).append(answer_index)
    return [
        tuple(group)
        for feedback_code, group in groups.items()
        if not (
            feedback_code == _FEEDBACK_PATTERN_COUNT - 1
            and len(group) == 1
            and group[0] == guess_index
        )
    ]


def _rank_partition_guesses(
    possible_indices: list[int],
    guessed_indices: set[int],
    matrix: FeedbackMatrix,
) -> list[int]:
    answer_indices = np.asarray(possible_indices, dtype=np.intp)
    candidate_count = matrix.shape[0]
    costs = np.full(candidate_count, np.iinfo(np.int64).max, dtype=np.int64)
    possible_set = set(possible_indices)

    for start in range(0, candidate_count, _MATRIX_CHUNK_SIZE):
        stop = min(start + _MATRIX_CHUNK_SIZE, candidate_count)
        guess_indices = [
            index for index in range(start, stop)
            if index not in guessed_indices
        ]
        if not guess_indices:
            continue
        feedbacks = matrix[
            np.asarray(guess_indices)[:, None],
            answer_indices,
        ]
        offsets = (
            np.arange(len(guess_indices), dtype=np.int32)[:, None]
            * _FEEDBACK_PATTERN_COUNT
        )
        grouped = np.bincount(
            (feedbacks.astype(np.int32) + offsets).ravel(),
            minlength=len(guess_indices) * _FEEDBACK_PATTERN_COUNT,
        ).reshape(len(guess_indices), _FEEDBACK_PATTERN_COUNT)
        costs[np.asarray(guess_indices)] = np.sum(
            grouped * grouped,
            axis=1,
            dtype=np.int64,
        )

    candidate_indices = np.flatnonzero(costs < np.iinfo(np.int64).max)
    return sorted(
        candidate_indices.tolist(),
        key=lambda index: (
            int(costs[index]),
            index not in possible_set,
            index,
        ),
    )


def _largest_four_letter_cluster(words: list[str]) -> int:
    pattern_counts: dict[str, int] = {}
    for word in words:
        for position in range(len(word)):
            pattern = f"{word[:position]}_{word[position + 1:]}"
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
    return max(pattern_counts.values(), default=0)


def prepare_bounded_guess_overrides(
    word_list: list[str],
    max_attempts: int = 6,
) -> tuple[dict[tuple[str, bytes], int], list[tuple[int, int, str, int]]]:
    """Find safer second guesses for opener branches whose p=2 policy exceeds the limit.

    Only branches with a repeated four-letter candidate pattern are inspected.
    For each, the p=2 continuation is followed over every feedback outcome; a
    replacement is accepted only when all outcomes fit within ``max_attempts``.
    """
    normalized_words = [word.strip().upper() for word in word_list]
    if max_attempts < 2:
        raise ValueError("max_attempts deve ser at least 2.")
    matrix, _, word_key = _get_feedback_matrix(normalized_words)
    possible_indices = list(range(len(normalized_words)))
    first_guess_index = _FIRST_GUESS_CACHE.get(word_key, -1)
    if first_guess_index < 0:
        first_guess_index = _choose_partition_guess(
            possible_indices,
            set(),
            matrix,
            word_key,
        )
        _FIRST_GUESS_CACHE[word_key] = first_guess_index

    initial_feedbacks = matrix[first_guess_index, :]
    branch_groups: dict[int, list[int]] = {}
    for answer_index, feedback_code in enumerate(initial_feedbacks):
        branch_groups.setdefault(int(feedback_code), []).append(answer_index)

    depth_cache: dict[tuple[tuple[int, ...], tuple[int, ...]], int] = {}

    def greedy_worst_case_depth(
        state: tuple[int, ...],
        used_guesses: tuple[int, ...],
    ) -> int:
        if len(state) == 1:
            return 1
        cache_key = state, used_guesses
        cached_depth = depth_cache.get(cache_key)
        if cached_depth is not None:
            return cached_depth
        guess_index = _choose_partition_guess(
            list(state),
            set(used_guesses),
            matrix,
            word_key,
        )
        next_used = tuple(sorted((*used_guesses, guess_index)))
        children = _partition_children(state, guess_index, matrix)
        worst_depth = 1 + max(
            (
                greedy_worst_case_depth(child, next_used)
                for child in children
            ),
            default=0,
        )
        depth_cache[cache_key] = worst_depth
        return worst_depth

    remaining_attempts = max_attempts - 1
    overrides: dict[tuple[str, bytes], int] = {}
    report: list[tuple[int, int, str, int]] = []
    initial_used = (first_guess_index,)

    for state_list in branch_groups.values():
        if len(state_list) <= 1:
            continue
        if _largest_four_letter_cluster(
            [normalized_words[index] for index in state_list]
        ) < 10:
            continue
        state = tuple(state_list)
        baseline_depth = greedy_worst_case_depth(state, initial_used)
        if baseline_depth <= remaining_attempts:
            continue

        for guess_index in _rank_partition_guesses(
            state_list,
            set(initial_used),
            matrix,
        ):
            children = _partition_children(state, guess_index, matrix)
            next_used = tuple(sorted((*initial_used, guess_index)))
            worst_depth = 1 + max(
                (
                    greedy_worst_case_depth(child, next_used)
                    for child in children
                ),
                default=0,
            )
            if worst_depth <= remaining_attempts:
                overrides[(word_key, _candidate_state_key(state_list))] = guess_index
                report.append(
                    (
                        len(state),
                        baseline_depth + 1,
                        normalized_words[guess_index],
                        worst_depth + 1,
                    )
                )
                break

    return overrides, report


def _build_feedback_matrix(word_list: list[str], path: Path) -> None:
    word_count = len(word_list)
    if not word_count:
        raise ValueError("A lista de palavras não pode estar vazia.")
    scoring_words = [t.normalize_word(word) for word in word_list]
    if any(
        len(word) != 5 or any(not "A" <= letter <= "Z" for letter in word)
        for word in scoring_words
    ):
        raise ValueError("A matriz de feedback exige palavras de cinco letras A-Z.")

    encoded_words = np.frombuffer(
        "".join(scoring_words).encode("ascii"),
        dtype=np.uint8,
    ).reshape(word_count, 5) - ord("A")
    answer_letter_counts = np.stack(
        [np.count_nonzero(encoded_words == letter, axis=1) for letter in range(26)],
        axis=1,
    )
    matrix = np.lib.format.open_memmap(
        path,
        mode="w+",
        dtype=np.uint8,
        shape=(word_count, word_count),
    )
    powers = np.array([1, 3, 9, 27, 81], dtype=np.uint8)

    for guess_index, guess in enumerate(encoded_words):
        green = encoded_words == guess
        marks = green.astype(np.uint8) * 2
        green_counts = {
            int(letter): green[:, guess == letter].sum(axis=1)
            for letter in np.unique(guess)
        }
        consumed_yellows: dict[int, np.ndarray] = {}
        for position, letter_value in enumerate(guess):
            letter = int(letter_value)
            if letter not in consumed_yellows:
                consumed_yellows[letter] = np.zeros(word_count, dtype=np.uint8)
            available = (
                answer_letter_counts[:, letter]
                - green_counts[letter]
                - consumed_yellows[letter]
            )
            yellow = ~green[:, position] & (available > 0)
            marks[yellow, position] = 1
            consumed_yellows[letter] += yellow
        matrix[guess_index] = np.sum(
            marks * powers,
            axis=1,
            dtype=np.uint16,
        ).astype(np.uint8)

    matrix.flush()
    del matrix


def _get_feedback_matrix(word_list: list[str]) -> tuple[FeedbackMatrix, dict[str, int], str]:
    normalized_words = [word.strip().upper() for word in word_list]
    key = _words_key(normalized_words)
    if key in _FEEDBACK_MATRIX_CACHE:
        return _FEEDBACK_MATRIX_CACHE[key], _WORD_INDEX_CACHE[key], key

    cache_path = DATASET_PATH.parent / f"feedback_matrix_{key}.npy"
    matrix: FeedbackMatrix | None = None
    if cache_path.exists():
        try:
            cached_matrix = np.load(cache_path, mmap_mode="r")
        except (OSError, ValueError):
            cached_matrix = None
        if cached_matrix is not None:
            if (
                cached_matrix.shape == (len(normalized_words), len(normalized_words))
                and cached_matrix.dtype == np.uint8
            ):
                matrix = cached_matrix
            else:
                del cached_matrix

    if matrix is None:
        temporary_path = cache_path.with_name(f"{cache_path.stem}.tmp.npy")
        _build_feedback_matrix(normalized_words, temporary_path)
        temporary_path.replace(cache_path)
        matrix = np.load(cache_path, mmap_mode="r")

    index = {word: position for position, word in enumerate(normalized_words)}
    if key not in _MATRIX_VALIDATED:
        rng = random.Random(0)
        for _ in range(3000):
            guess_index = rng.randrange(len(normalized_words))
            answer_index = rng.randrange(len(normalized_words))
            expected = _feedback_code(
                t.score_guess(normalized_words[answer_index], normalized_words[guess_index])
            )
            if int(matrix[guess_index, answer_index]) != expected:
                raise RuntimeError(
                    "A matriz pré-calculada diverge de score_guess para "
                    f"{normalized_words[guess_index]!r}/{normalized_words[answer_index]!r}."
                )
        _MATRIX_VALIDATED.add(key)

    _FEEDBACK_MATRIX_CACHE[key] = matrix
    _WORD_INDEX_CACHE[key] = index
    return matrix, index, key


def _choose_partition_guess(
    possible_indices: list[int],
    guessed_indices: set[int],
    matrix: FeedbackMatrix,
    word_key: str,
) -> int:
    state_digest = hashlib.sha256(
        np.asarray(possible_indices, dtype=np.uint32).tobytes()
    ).digest()
    cache_key = word_key, state_digest, tuple(sorted(guessed_indices))
    cached_index = _PARTITION_GUESS_CACHE.get(cache_key)
    if cached_index is not None:
        return cached_index

    answer_indices = np.asarray(possible_indices, dtype=np.intp)
    possible_set = set(possible_indices)
    best_cost: float | None = None
    best_indices: list[int] = []
    candidate_count = matrix.shape[0]

    for start in range(0, candidate_count, _MATRIX_CHUNK_SIZE):
        stop = min(start + _MATRIX_CHUNK_SIZE, candidate_count)
        guess_indices = [
            index for index in range(start, stop)
            if index not in guessed_indices
        ]
        if not guess_indices:
            continue

        feedbacks = matrix[
            np.asarray(guess_indices)[:, None],
            answer_indices,
        ]
        offsets = (
            np.arange(len(guess_indices), dtype=np.int32)[:, None]
            * _FEEDBACK_PATTERN_COUNT
        )
        grouped = np.bincount(
            (feedbacks.astype(np.int32) + offsets).ravel(),
            minlength=len(guess_indices) * _FEEDBACK_PATTERN_COUNT,
        ).reshape(len(guess_indices), _FEEDBACK_PATTERN_COUNT)
        costs = np.sum(grouped * grouped, axis=1, dtype=np.int64)
        chunk_best = int(costs.min())
        if best_cost is None or chunk_best < best_cost:
            best_cost = chunk_best
            best_indices = [
                guess_indices[index]
                for index in np.flatnonzero(costs == chunk_best)
            ]
        elif chunk_best == best_cost:
            best_indices.extend(
                guess_indices[index]
                for index in np.flatnonzero(costs == chunk_best)
            )

    if not best_indices:
        raise RuntimeError("Não há palpites aceitos ainda não utilizados.")
    selected_index = next(
        (index for index in best_indices if index in possible_set),
        best_indices[0],
    )
    _PARTITION_GUESS_CACHE[cache_key] = selected_index
    return selected_index
