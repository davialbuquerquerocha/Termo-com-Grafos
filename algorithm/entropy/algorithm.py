"""Solver orchestration and command-line interface for Termo."""

import argparse
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import random
import re
import tempfile
import uuid
from time import perf_counter
from typing import Literal, NamedTuple

import numpy as np

from algorithm.partition import functions as partition_functions
from . import functions as helpers

Strategy = Literal["entropy", "groups", "deep"]
AnswerList = Literal["accepted", "solutions"]
GuessSelector = Callable[[list[str]], int]

_ENTROPY_GUESS_CACHE: OrderedDict[
    tuple[str, int, int, tuple[str, ...]], int
] = OrderedDict()
_SearchContext = tuple[
    list[str],
    dict[str, int],
    partition_functions.FeedbackMatrix,
    str,
]
_WORKER_ANSWERS: list[str] = []
_WORKER_STRATEGY: Strategy | None = None
_WORKER_CONTEXT: _SearchContext | None = None
_WORKER_MEMO_PATH: Path | None = None
_WORKER_INITIAL_GUESS_INDEX: int | None = None
_WORKER_PROFILE = False
_WORKER_ROOT_CANDIDATES: list[str] | None = None
_WORKER_ROOT_DEPTH = 0
_GROUP_PROGRESS_INTERVAL = 10_000_000
_WORKER_GROUP_PROGRESS_COUNT = 0
_RUN_LOG_HEARTBEAT_SECONDS = 30


class SolverEvaluation(NamedTuple):
    average_attempts: float
    worst_case: int
    worst_answers: tuple[str, ...]
    distribution: dict[int, int]
    win_rate_up_to_six: float
    total_games: int


__all__ = [
    "AnswerList",
    "SolverEvaluation",
    "Strategy",
    "best_move",
    "choose_first_guess",
    "choose_guess",
    "evaluate_guess",
    "evaluate_solver",
    "interactive_play",
    "main",
    "simulate_game",
]


def _append_runtime_log(
    path: Path,
    run_id: str,
    event: str,
    **details: object,
) -> None:
    record = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "run_id": run_id,
        "pid": os.getpid(),
        "event": event,
        **details,
    }
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _validate_strategy(strategy: str) -> Strategy:
    if strategy == "entropy":
        return "entropy"
    if strategy in ("groups", "deep"):
        return "deep"
    raise ValueError(
        "strategy must be 'entropy' for entropy-only selection or "
        "'groups' to recursively analyze feedback groups."
    )


def _search_settings() -> dict[str, int | float | None]:
    return {
        "algorithm_version": helpers.SEARCH_ALGORITHM_VERSION,
        "max_attempts": helpers.MAX_ATTEMPTS,
        "exhaustive_limit": helpers.EXHAUSTIVE_LIMIT,
        "budget": helpers.BUDGET,
        "factor": helpers.FACTOR,
        "min_k": helpers.MIN_K,
        "max_k": helpers.MAX_K,
        "entropy_margin": helpers.ENTROPY_MARGIN,
    }


def _normalize_candidates(candidates: list[str]) -> list[str]:
    return list(
        dict.fromkeys(candidate.strip().upper() for candidate in candidates)
    )


def _answer_list_path(answer_list: AnswerList) -> Path:
    if answer_list == "accepted":
        return partition_functions.DATASET_PATH
    if answer_list == "solutions":
        return partition_functions.DATASET_PATH.with_name(
            "termo_solucoes_possiveis.txt"
        )
    raise ValueError("answer_list must be 'accepted' or 'solutions'.")


def _load_answers(answer_list: AnswerList = "accepted") -> list[str]:
    with _answer_list_path(answer_list).open(encoding="utf-8") as word_file:
        answers = _normalize_candidates(word_file.readlines())
    if not answers:
        raise ValueError("The answer list must not be empty.")
    return answers


def _load_guess_words(candidates: list[str]) -> list[str]:
    with partition_functions.DATASET_PATH.open(encoding="utf-8") as word_file:
        guesses = _normalize_candidates(word_file.readlines())
    for candidate in candidates:
        normalized_candidate = candidate.strip().upper()
        if normalized_candidate not in guesses:
            guesses.append(normalized_candidate)
    return guesses


def _search_context(
    candidates: list[str],
    memo_path: Path | None = None,
) -> _SearchContext:
    guesses = _load_guess_words(candidates)
    matrix, word_indices, word_key = partition_functions._get_feedback_matrix(
        guesses
    )
    helpers.configure_memo_store(
        memo_path
        if memo_path is not None
        else partition_functions.DATASET_PATH.with_name("entropy_memo.sqlite3"),
        word_key,
    )
    return guesses, word_indices, matrix, word_key


def best_move(
    candidates: list[str],
    depth: int = 0,
    workers: int = 1,
) -> tuple[int, float]:
    """Return the best guess index and expected number of guesses."""
    if depth < 0:
        raise ValueError("depth must be non-negative.")
    if workers <= 0:
        raise ValueError("workers must be greater than zero.")
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")
    context = _search_context(normalized_candidates)
    if workers == 1:
        result = helpers._best_move(normalized_candidates, depth, context)
    else:
        result = helpers._best_move(
            normalized_candidates,
            depth,
            context,
            parallel_evaluator=lambda root_candidates, ranked_guesses, root_depth, root_context: (
                _parallel_root_evaluator(
                    root_candidates,
                    ranked_guesses,
                    root_depth,
                    root_context,
                    workers,
                )
            ),
        )
    if result[0] < 0 or not math.isfinite(result[1]):
        raise RuntimeError(
            "No groups strategy can guarantee solving within "
            f"{helpers.MAX_ATTEMPTS} guesses from this candidate state."
        )
    return result


def evaluate_guess(i: int, candidates: list[str], limit: float) -> float:
    """Evaluate the expected cost of trying guess index ``i``."""
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")
    context = _search_context(normalized_candidates)
    if i < 0 or i >= len(context[0]):
        raise IndexError("guess index is outside the guess list.")
    return helpers._evaluate_guess(i, normalized_candidates, limit, 0, context)


def choose_first_guess(
    workers: int = 1,
    answer_list: AnswerList = "accepted",
) -> tuple[int, float]:
    """Load or calculate the deep-search first guess and persist its result."""
    if workers <= 0:
        raise ValueError("workers must be greater than zero.")
    word_list_path = _answer_list_path(answer_list)
    word_list_content = word_list_path.read_bytes()
    word_list_hash = hashlib.sha256(word_list_content).hexdigest()
    candidates = _normalize_candidates(
        word_list_content.decode("utf-8").splitlines()
    )
    guess_words = _load_guess_words(candidates)
    guess_list_hash = hashlib.sha256(
        partition_functions.DATASET_PATH.read_bytes()
    ).hexdigest()
    if not candidates:
        raise ValueError("The answer list must not be empty.")

    cache_path = word_list_path.with_name(
        f"entropy_first_guess_{answer_list}.json"
    )
    if cache_path.exists():
        cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached_data, dict):
            raise ValueError(f"Invalid first-guess cache format in {cache_path}.")
        if cached_data.get("word_list_hash") == word_list_hash:
            if (
                cached_data.get("answer_list") != answer_list
                or cached_data.get("guess_list_hash") != guess_list_hash
                or cached_data.get("search_settings") != _search_settings()
            ):
                cached_data = {}
        if cached_data.get("word_list_hash") == word_list_hash:
            guess = cached_data.get("guess")
            expected_cost = cached_data.get("expected_cost")
            if (
                not isinstance(guess, str)
                or not isinstance(expected_cost, (int, float))
                or isinstance(expected_cost, bool)
                or not math.isfinite(expected_cost)
                or expected_cost <= 0
            ):
                raise ValueError(f"Invalid first-guess cache values in {cache_path}.")
            try:
                return guess_words.index(guess), float(expected_cost)
            except ValueError as error:
                raise ValueError(
                    f"Cached first guess {guess!r} is absent from the guess vocabulary."
                ) from error

    print(
        "Calculando o primeiro palpite de groups; "
        "a busca inicial pode ser demorada.",
        flush=True,
    )
    guess_index, expected_cost = best_move(candidates, workers=workers)
    if not 0 <= guess_index < len(guess_words):
        raise RuntimeError("best_move returned an index outside the guess vocabulary.")
    if not math.isfinite(expected_cost) or expected_cost <= 0:
        raise RuntimeError("best_move returned an invalid expected cost.")

    guess = guess_words[guess_index]
    cache_data = {
        "word_list_hash": word_list_hash,
        "answer_list": answer_list,
        "guess_list_hash": guess_list_hash,
        "search_settings": _search_settings(),
        "guess": guess,
        "expected_cost": expected_cost,
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=cache_path.parent,
            prefix=f"{cache_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as cache_file:
            temporary_path = Path(cache_file.name)
            json.dump(cache_data, cache_file, ensure_ascii=False, indent=2)
            cache_file.write("\n")
        temporary_path.replace(cache_path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return guess_index, float(expected_cost)


def choose_guess(
    candidates: list[str],
    strategy: Strategy = "entropy",
    depth: int = 0,
) -> int:
    """Select by entropy alone or by recursively analyzing feedback groups."""
    strategy = _validate_strategy(strategy)
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")

    if strategy == "deep":
        return best_move(normalized_candidates, depth)[0]

    context = _search_context(normalized_candidates)
    return _choose_guess_with_context(
        normalized_candidates,
        strategy,
        depth,
        context,
    )


def _choose_guess_with_context(
    candidates: list[str],
    strategy: Strategy,
    depth: int,
    context: _SearchContext,
) -> int:
    if strategy == "deep":
        guess_index, _ = helpers._best_move(candidates, depth, context)
        if guess_index < 0:
            raise RuntimeError(
                "No groups strategy can guarantee solving within "
                f"{helpers.MAX_ATTEMPTS} guesses from this candidate state."
            )
        return guess_index

    word_list_path = partition_functions.DATASET_PATH
    word_list_stat = word_list_path.stat()
    cache_key = (
        str(word_list_path),
        word_list_stat.st_mtime_ns,
        word_list_stat.st_size,
        tuple(candidates),
    )
    cached_guess = _ENTROPY_GUESS_CACHE.get(cache_key)
    if cached_guess is not None:
        _ENTROPY_GUESS_CACHE.move_to_end(cache_key)
        return cached_guess

    ranked_guesses = helpers.ranking_with_context(candidates, 1, context)
    guess_index = (
        ranked_guesses[-1]
        if len(candidates) == 1
        else ranked_guesses[0]
    )
    _ENTROPY_GUESS_CACHE[cache_key] = guess_index
    _ENTROPY_GUESS_CACHE.move_to_end(cache_key)
    while len(_ENTROPY_GUESS_CACHE) > helpers.MEMO_MEMORY_LIMIT:
        _ENTROPY_GUESS_CACHE.popitem(last=False)
    return guess_index


def _expected_cost(
    guess_index: int,
    candidates: list[str],
    strategy: Strategy,
    depth: int = 0,
    context: _SearchContext | None = None,
) -> float:
    if strategy == "deep":
        if context is None:
            return best_move(candidates, depth)[1]
        return helpers._best_move(candidates, depth, context)[1]
    if context is None:
        context = _search_context(candidates)
    _, word_indices, matrix, _ = context
    normalized_candidates = _normalize_candidates(candidates)
    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in normalized_candidates),
        dtype=np.intp,
        count=len(normalized_candidates),
    )
    feedback_codes = matrix[guess_index, candidate_indices]
    counts = np.bincount(feedback_codes)
    counts = counts[counts > 0]
    probabilities = counts / len(normalized_candidates)
    return float(-np.sum(probabilities * np.log2(probabilities)))


def interactive_play(
    strategy: Strategy = "entropy",
    answer_list: AnswerList = "accepted",
) -> str:
    """Play using entropy only or recursively analyzed feedback groups."""
    strategy = _validate_strategy(strategy)
    candidates = _load_answers(answer_list)
    context = _search_context(candidates)
    guesses, word_indices, matrix, _ = context
    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    initial_deep_guess = (
        choose_first_guess(answer_list=answer_list)
        if strategy == "deep"
        else None
    )
    depth = 0

    while candidates:
        if depth == 0 and initial_deep_guess is not None:
            guess_index, expected_cost = initial_deep_guess
        else:
            if strategy == "deep":
                guess_index, expected_cost = helpers._best_move(
                    candidates,
                    depth,
                    context,
                )
                if guess_index < 0:
                    raise RuntimeError(
                        "No groups strategy can guarantee solving within "
                        f"{helpers.MAX_ATTEMPTS} guesses from this candidate state."
                    )
            else:
                guess_index = _choose_guess_with_context(
                    candidates,
                    strategy,
                    depth,
                    context,
                )
                expected_cost = _expected_cost(
                    guess_index,
                    candidates,
                    strategy,
                    depth,
                    context,
                )

        guess = guesses[guess_index]
        score_name = "entropia (bits)" if strategy == "entropy" else "custo esperado"
        print(f"Palpite sugerido: {guess} ({score_name}: {expected_cost:.2f})")

        candidate_indices = np.fromiter(
            (word_indices[candidate] for candidate in candidates),
            dtype=np.intp,
            count=len(candidates),
        )
        guess_feedbacks = matrix[word_indices[guess], candidate_indices]

        while True:
            entered_feedback = input("Feedback (P=preto, A=amarelo, V=verde): ")
            try:
                feedback_code = helpers.parse_feedback(entered_feedback)
            except ValueError as error:
                print(f"Feedback inválido: {error}")
                continue

            next_candidates = [
                candidate
                for candidate, actual_code in zip(candidates, guess_feedbacks)
                if int(actual_code) == feedback_code
            ]
            if not next_candidates:
                print(
                    "Esse feedback não corresponde a nenhuma candidata atual. "
                    "Confira as cores e tente novamente."
                )
                continue
            break

        if feedback_code == winning_feedback:
            print(f"Jogo resolvido: {guess}")
            return guess
        candidates = next_candidates
        depth += 1
        print(f"Candidatas restantes: {len(candidates)}")

    raise RuntimeError("The candidate set became empty.")


def simulate_game(
    answer: str,
    strategy: Strategy = "entropy",
    answer_list: AnswerList = "accepted",
) -> int:
    """Simulate a game with entropy-only or feedback-group analysis."""
    strategy = _validate_strategy(strategy)
    normalized_answer = answer.strip().upper()
    candidates = _load_answers(answer_list)
    if normalized_answer not in candidates:
        raise ValueError(
            f"The answer {normalized_answer!r} is not in the selected answer list."
        )

    context = _search_context(candidates)
    initial_deep_guess = (
        choose_first_guess(answer_list=answer_list)
        if strategy == "deep"
        else None
    )
    initial_guess_index = initial_deep_guess[0] if initial_deep_guess else None
    return _simulate_game_with_context(
        normalized_answer,
        candidates,
        strategy,
        context,
        initial_guess_index,
    )


def _simulate_game_with_context(
    answer: str,
    all_answers: list[str],
    strategy: Strategy,
    context: _SearchContext,
    initial_guess_index: int | None = None,
    guess_history: list[dict[str, str]] | None = None,
) -> int:
    guesses, word_indices, matrix, _ = context
    candidates = all_answers.copy()
    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    answer_index = word_indices[answer]
    guess_index = (
        initial_guess_index
        if initial_guess_index is not None
        else _choose_guess_with_context(candidates, strategy, 0, context)
    )
    attempts = 0

    while True:
        attempts += 1
        feedback_code = int(matrix[guess_index, answer_index])
        if guess_history is not None:
            guess_history.append(
                {
                    "guess": guesses[guess_index],
                    "feedback": _feedback_text(feedback_code),
                }
            )
        if feedback_code == winning_feedback:
            return attempts

        candidate_indices = np.fromiter(
            (word_indices[candidate] for candidate in candidates),
            dtype=np.intp,
            count=len(candidates),
        )
        matching_indices = candidate_indices[
            matrix[guess_index, candidate_indices] == feedback_code
        ]
        if not len(matching_indices):
            raise RuntimeError("Feedback removed every possible answer.")
        if len(matching_indices) == len(candidates):
            raise RuntimeError(
                f"Guess {guesses[guess_index]!r} did not narrow the candidate set."
            )
        if strategy == "deep" and attempts >= helpers.MAX_ATTEMPTS:
            raise RuntimeError(
                "The groups strategy failed to solve the answer within "
                f"{helpers.MAX_ATTEMPTS} guesses."
            )
        candidates = [guesses[int(index)] for index in matching_indices]
        guess_index = _choose_guess_with_context(
            candidates,
            strategy,
            attempts,
            context,
        )


def _feedback_text(feedback_code: int) -> str:
    feedback_marks = ("P", "A", "V")
    return "".join(
        feedback_marks[(feedback_code // (3**position)) % 3]
        for position in range(5)
    )


def _simulate_and_capture_game(
    answer: str,
    all_answers: list[str],
    strategy: Strategy,
    context: _SearchContext,
    initial_guess_index: int | None,
) -> tuple[int, list[dict[str, str]]]:
    guess_history: list[dict[str, str]] = []
    attempts = _simulate_game_with_context(
        answer,
        all_answers,
        strategy,
        context,
        initial_guess_index,
        guess_history,
    )
    return attempts, guess_history


def _initialize_evaluation_worker(
    all_answers: list[str],
    strategy: Strategy,
    dataset_path: Path,
    memo_path: Path,
    worker_count: int,
    initial_guess_index: int | None,
    collect_profile: bool,
    root_candidates: list[str] | None = None,
    root_depth: int = 0,
    max_k: int | None = None,
) -> None:
    global _WORKER_ANSWERS, _WORKER_STRATEGY, _WORKER_CONTEXT
    global _WORKER_MEMO_PATH, _WORKER_INITIAL_GUESS_INDEX, _WORKER_PROFILE
    global _WORKER_ROOT_CANDIDATES, _WORKER_ROOT_DEPTH
    global _WORKER_GROUP_PROGRESS_COUNT
    helpers.MAX_K = max_k
    partition_functions.DATASET_PATH = dataset_path
    process_name = multiprocessing.current_process().name
    worker_match = re.search(r"-(\d+)$", process_name)
    if worker_match is None:
        raise RuntimeError(f"Unable to identify evaluation worker {process_name!r}.")
    worker_slot = (int(worker_match.group(1)) - 1) % worker_count
    worker_memo_path = memo_path.with_name(
        f"{memo_path.stem}_{worker_count}_{worker_slot}{memo_path.suffix}"
    )
    _WORKER_ANSWERS = all_answers
    _WORKER_STRATEGY = strategy
    _WORKER_MEMO_PATH = worker_memo_path
    _WORKER_INITIAL_GUESS_INDEX = initial_guess_index
    _WORKER_PROFILE = collect_profile
    _WORKER_ROOT_CANDIDATES = root_candidates
    _WORKER_ROOT_DEPTH = root_depth
    _WORKER_GROUP_PROGRESS_COUNT = 0
    _WORKER_CONTEXT = _search_context(all_answers, worker_memo_path)


def _process_root_feedback_group(
    feedback_group: tuple[int, list[str]],
) -> tuple[int, int, float, helpers.SearchProfile | None]:
    if _WORKER_CONTEXT is None or _WORKER_MEMO_PATH is None:
        raise RuntimeError("The search worker was not initialized.")

    feedback_code, candidates = feedback_group
    helpers.configure_memo_store(_WORKER_MEMO_PATH, _WORKER_CONTEXT[3])
    try:
        if _WORKER_PROFILE:
            with helpers.profile_search() as profile:
                _, cost = helpers._best_move(
                    candidates,
                    _WORKER_ROOT_DEPTH + 1,
                    _WORKER_CONTEXT,
                    group_progress_callback=_worker_group_progress_reporter,
                )
            return feedback_code, len(candidates), cost, profile

        _, cost = helpers._best_move(
            candidates,
            _WORKER_ROOT_DEPTH + 1,
            _WORKER_CONTEXT,
            group_progress_callback=_worker_group_progress_reporter,
        )
        return feedback_code, len(candidates), cost, None
    finally:
        helpers.close_memo_store()


def _worker_group_progress_reporter() -> None:
    global _WORKER_GROUP_PROGRESS_COUNT
    _WORKER_GROUP_PROGRESS_COUNT += 1
    if _WORKER_GROUP_PROGRESS_COUNT % _GROUP_PROGRESS_INTERVAL == 0:
        process_name = multiprocessing.current_process().name
        print(
            f"{process_name}: {_WORKER_GROUP_PROGRESS_COUNT} grupos "
            "recursivos concluídos dentro do palpite base.",
            flush=True,
        )


def _process_root_guess_batch(
    guesses: list[tuple[int, float]],
) -> tuple[list[tuple[int, float]], helpers.SearchProfile | None]:
    if _WORKER_CONTEXT is None or _WORKER_MEMO_PATH is None:
        raise RuntimeError("The search worker was not initialized.")
    if _WORKER_ROOT_CANDIDATES is None:
        raise RuntimeError("The root search worker has no candidate state.")

    helpers.configure_memo_store(_WORKER_MEMO_PATH, _WORKER_CONTEXT[3])
    results: list[tuple[int, float]] = []
    try:
        process_name = multiprocessing.current_process().name
        if _WORKER_PROFILE:
            with helpers.profile_search() as profile:
                for guess_index, limit in guesses:
                    print(
                        f"{process_name}: avaliando palpite "
                        f"{_WORKER_CONTEXT[0][guess_index]} e seus grupos.",
                        flush=True,
                    )
                    started = perf_counter()
                    cost = helpers._evaluate_guess(
                        guess_index,
                        _WORKER_ROOT_CANDIDATES,
                        limit,
                        _WORKER_ROOT_DEPTH,
                        _WORKER_CONTEXT,
                    )
                    profile.guess_evaluations += 1
                    profile.evaluation_seconds += perf_counter() - started
                    results.append((guess_index, cost))
            return results, profile

        for guess_index, limit in guesses:
            print(
                f"{process_name}: avaliando palpite "
                f"{_WORKER_CONTEXT[0][guess_index]} e seus grupos.",
                flush=True,
            )
            cost = helpers._evaluate_guess(
                guess_index,
                _WORKER_ROOT_CANDIDATES,
                limit,
                _WORKER_ROOT_DEPTH,
                _WORKER_CONTEXT,
            )
            results.append((guess_index, cost))
        return results, None
    finally:
        helpers.close_memo_store()


def _parallel_root_evaluator(
    candidates: list[str],
    ranked_guesses: list[int],
    depth: int,
    context: _SearchContext,
    workers: int,
) -> tuple[int, float]:
    best_guess = -1
    best_cost = float("inf")
    if not ranked_guesses:
        return best_guess, best_cost

    first_guess = ranked_guesses[0]
    started = perf_counter()
    guess = context[0][first_guess]
    print(
        f"Busca inicial: avaliando palpite base "
        f"{guess} (1/{len(ranked_guesses)}) "
        "e seus grupos recursivos.",
        flush=True,
    )
    feedback_groups = _partition_feedback_groups(first_guess, candidates, context)
    remaining_guesses = ranked_guesses[1:]
    completed_guesses = 1
    can_parallelize_base = workers > 1 and len(feedback_groups) > 1
    if not can_parallelize_base:
        best_cost = helpers._evaluate_guess(
            first_guess,
            candidates,
            best_cost,
            depth,
            context,
            group_progress_callback=_group_progress_reporter(guess),
        )
        if helpers._PROFILE is not None:
            helpers._PROFILE.guess_evaluations += 1
            helpers._PROFILE.evaluation_seconds += perf_counter() - started
        if math.isfinite(best_cost):
            best_guess = first_guess
        if not remaining_guesses:
            return best_guess, best_cost

    if can_parallelize_base:
        worker_count = min(
            workers,
            max(len(feedback_groups), len(remaining_guesses)),
        )
    else:
        worker_count = min(workers, len(remaining_guesses))
    if helpers._PROFILE is not None:
        helpers._PROFILE.worker_processes = max(
            helpers._PROFILE.worker_processes,
            worker_count,
        )
    memo_base = partition_functions.DATASET_PATH.with_name(
        "entropy_memo_worker.sqlite3"
    )
    batch_size = 1
    wave_size = worker_count * batch_size
    with ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=multiprocessing.get_context("spawn"),
        initializer=_initialize_evaluation_worker,
        initargs=(
            context[0],
            "deep",
            partition_functions.DATASET_PATH,
            memo_base,
            worker_count,
            None,
            helpers._PROFILE is not None,
            candidates,
            depth,
            helpers.MAX_K,
        ),
    ) as executor:
        if can_parallelize_base:
            print(
                f"Busca inicial: distribuindo os {len(feedback_groups)} "
                f"grupos de feedback não resolvidos de {guess} entre "
                f"{worker_count} workers.",
                flush=True,
            )
            futures = {
                executor.submit(_process_root_feedback_group, group): group[0]
                for group in feedback_groups
            }
            completed_groups = 0
            group_costs: dict[int, tuple[int, float]] = {}
            while futures:
                completed, _ = wait(
                    futures,
                    return_when=FIRST_COMPLETED,
                )
                for future in completed:
                    feedback_code = futures.pop(future)
                    result_feedback, group_size, group_cost, worker_profile = (
                        future.result()
                    )
                    if feedback_code != result_feedback:
                        raise RuntimeError(
                            "A root feedback worker returned the wrong group."
                        )
                    if (
                        helpers._PROFILE is not None
                        and worker_profile is not None
                    ):
                        _merge_worker_profile(helpers._PROFILE, worker_profile)
                    group_costs[feedback_code] = (group_size, group_cost)
                    completed_groups += 1
                    print(
                        f"Busca inicial: grupo {_feedback_text(feedback_code)} "
                        f"do palpite {guess} concluído "
                        f"({completed_groups}/{len(feedback_groups)}).",
                        flush=True,
                    )

            base_cost = 1.0
            for feedback_code, _ in feedback_groups:
                group_size, group_cost = group_costs[feedback_code]
                base_cost += group_size * group_cost / len(candidates)
            if helpers._PROFILE is not None:
                helpers._PROFILE.guess_evaluations += 1
                helpers._PROFILE.evaluation_seconds += perf_counter() - started
            if math.isfinite(base_cost):
                best_guess = first_guess
                best_cost = base_cost

        if not remaining_guesses:
            return best_guess, best_cost
        print(
            f"Busca inicial: palpite base concluído; "
            f"avaliando os outros {len(remaining_guesses)} palpites em paralelo.",
            flush=True,
        )

        for wave_start in range(0, len(remaining_guesses), wave_size):
            wave = remaining_guesses[wave_start:wave_start + wave_size]
            tasks = [
                [
                    (guess_index, best_cost)
                    for guess_index in wave[index:index + batch_size]
                ]
                for index in range(0, len(wave), batch_size)
            ]
            futures = {
                executor.submit(_process_root_guess_batch, task): task[0][0]
                for task in tasks
            }
            while futures:
                completed, _ = wait(
                    futures,
                    return_when=FIRST_COMPLETED,
                )
                for future in completed:
                    batch_results, worker_profile = future.result()
                    if (
                        helpers._PROFILE is not None
                        and worker_profile is not None
                    ):
                        _merge_worker_profile(helpers._PROFILE, worker_profile)
                    for guess_index, cost in batch_results:
                        if cost < best_cost:
                            best_guess = guess_index
                            best_cost = cost
                    completed_guess_index = futures.pop(future)
                    completed_guesses += 1
                    print(
                        f"Busca inicial: palpite "
                        f"{context[0][completed_guess_index]} concluído; "
                        f"{completed_guesses}/{len(ranked_guesses)} "
                        "palpites avaliados.",
                        flush=True,
                    )
    return best_guess, best_cost


def _partition_feedback_groups(
    guess_index: int,
    candidates: list[str],
    context: _SearchContext,
) -> list[tuple[int, list[str]]]:
    guesses, word_indices, matrix, _ = context
    candidate_indices = np.fromiter(
        (word_indices[candidate] for candidate in candidates),
        dtype=np.intp,
        count=len(candidates),
    )
    feedback_codes = matrix[
        word_indices[guesses[guess_index]],
        candidate_indices,
    ]
    groups: dict[int, list[str]] = {}
    for candidate, feedback_code in zip(candidates, feedback_codes):
        groups.setdefault(int(feedback_code), []).append(candidate)

    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    return sorted(
        (
            (feedback_code, group)
            for feedback_code, group in groups.items()
            if feedback_code != winning_feedback
        ),
        key=lambda item: len(item[1]),
    )


def _group_progress_reporter(guess: str) -> Callable[[], None]:
    completed_groups = 0

    def report_progress() -> None:
        nonlocal completed_groups
        completed_groups += 1
        if completed_groups % _GROUP_PROGRESS_INTERVAL == 0:
            print(
                f"Busca inicial: palpite base {guess}; "
                f"{completed_groups} grupos de feedback recursivos concluídos.",
                flush=True,
            )

    return report_progress


def _process_evaluation_batch(
    answers: list[str],
    batch_index: int = 0,
    runtime_log_path: Path | None = None,
    runtime_log_id: str | None = None,
) -> tuple[
    list[tuple[str, int, list[dict[str, str]]]],
    helpers.SearchProfile | None,
]:
    if (
        _WORKER_STRATEGY is None
        or _WORKER_CONTEXT is None
        or _WORKER_MEMO_PATH is None
    ):
        raise RuntimeError("The evaluation worker was not initialized.")

    helpers.configure_memo_store(
        _WORKER_MEMO_PATH,
        _WORKER_CONTEXT[3],
    )
    results: list[tuple[str, int, list[dict[str, str]]]] = []
    process_name = multiprocessing.current_process().name
    if runtime_log_path is not None and runtime_log_id is not None:
        _append_runtime_log(
            runtime_log_path,
            runtime_log_id,
            "worker_batch_started",
            batch_index=batch_index,
            batch_size=len(answers),
            worker=process_name,
        )
    try:
        if _WORKER_PROFILE:
            with helpers.profile_search() as profile:
                for answer_index, answer in enumerate(answers, start=1):
                    print(
                        f"{process_name}: iniciando resposta {answer} "
                        f"({answer_index}/{len(answers)} do lote "
                        f"{batch_index + 1}).",
                        flush=True,
                    )
                    if runtime_log_path is not None and runtime_log_id is not None:
                        _append_runtime_log(
                            runtime_log_path,
                            runtime_log_id,
                            "worker_answer_started",
                            batch_index=batch_index,
                            answer_index=answer_index,
                            batch_size=len(answers),
                            answer=answer,
                            worker=process_name,
                        )
                    attempts, guess_history = _simulate_and_capture_game(
                        answer,
                        _WORKER_ANSWERS,
                        _WORKER_STRATEGY,
                        _WORKER_CONTEXT,
                        _WORKER_INITIAL_GUESS_INDEX,
                    )
                    results.append((answer, attempts, guess_history))
                    print(
                        f"{process_name}: resposta {answer} concluída "
                        f"({answer_index}/{len(answers)} do lote "
                        f"{batch_index + 1}).",
                        flush=True,
                    )
                    if (
                        runtime_log_path is not None
                        and runtime_log_id is not None
                    ):
                        _append_runtime_log(
                            runtime_log_path,
                            runtime_log_id,
                            "worker_answer_completed",
                            batch_index=batch_index,
                            answer_index=answer_index,
                            batch_size=len(answers),
                            answer=answer,
                            attempts=attempts,
                            worker=process_name,
                        )
            return results, profile

        for answer_index, answer in enumerate(answers, start=1):
            print(
                f"{process_name}: iniciando resposta {answer} "
                f"({answer_index}/{len(answers)} do lote "
                f"{batch_index + 1}).",
                flush=True,
            )
            if runtime_log_path is not None and runtime_log_id is not None:
                _append_runtime_log(
                    runtime_log_path,
                    runtime_log_id,
                    "worker_answer_started",
                    batch_index=batch_index,
                    answer_index=answer_index,
                    batch_size=len(answers),
                    answer=answer,
                    worker=process_name,
                )
            attempts, guess_history = _simulate_and_capture_game(
                answer,
                _WORKER_ANSWERS,
                _WORKER_STRATEGY,
                _WORKER_CONTEXT,
                _WORKER_INITIAL_GUESS_INDEX,
            )
            results.append((answer, attempts, guess_history))
            print(
                f"{process_name}: resposta {answer} concluída "
                f"({answer_index}/{len(answers)} do lote "
                f"{batch_index + 1}).",
                flush=True,
            )
            if (
                runtime_log_path is not None
                and runtime_log_id is not None
            ):
                _append_runtime_log(
                    runtime_log_path,
                    runtime_log_id,
                    "worker_answer_completed",
                    batch_index=batch_index,
                    answer_index=answer_index,
                    batch_size=len(answers),
                    answer=answer,
                    attempts=attempts,
                    worker=process_name,
                )
        return results, None
    finally:
        helpers.close_memo_store()


def _merge_worker_profile(
    destination: helpers.SearchProfile,
    source: helpers.SearchProfile,
) -> None:
    destination.states_computed += source.states_computed
    destination.memo_hits += source.memo_hits
    destination.ranking_calls += source.ranking_calls
    destination.ranking_seconds += source.ranking_seconds
    destination.guess_evaluations += source.guess_evaluations
    destination.evaluation_seconds += source.evaluation_seconds
    destination.memo_reads += source.memo_reads
    destination.memo_writes += source.memo_writes


def _evaluation_json_path(
    strategy: Strategy,
    evaluation_key: str,
    word_key: str,
) -> Path:
    settings_json = json.dumps(
        _search_settings(),
        sort_keys=True,
        separators=(",", ":"),
    )
    settings_key = hashlib.sha256(settings_json.encode("utf-8")).hexdigest()[:12]
    return partition_functions.DATASET_PATH.with_name(
        f"entropy_games_{strategy}_{evaluation_key[:12]}_"
        f"{word_key[:12]}_{settings_key}.json"
    )


def _load_evaluation_json(
    path: Path,
    strategy: Strategy,
    evaluation_key: str,
    word_key: str,
) -> tuple[dict[str, int], dict[str, list[dict[str, str]]]]:
    if not path.exists():
        return {}, {}

    try:
        game_results = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Unable to read saved game sequences from {path}.") from error
    if (
        not isinstance(game_results, dict)
        or game_results.get("format_version") not in (1, 2)
        or game_results.get("strategy") != strategy
        or game_results.get("evaluation_key") != evaluation_key
        or game_results.get("word_list_key") != word_key
        or game_results.get("search_settings") != _search_settings()
        or not isinstance(game_results.get("games"), list)
    ):
        raise ValueError(f"Saved game sequence metadata is invalid in {path}.")

    attempts_by_answer: dict[str, int] = {}
    guess_histories: dict[str, list[dict[str, str]]] = {}
    for game in game_results["games"]:
        if not isinstance(game, dict):
            raise ValueError(f"Invalid game record in {path}.")
        answer = game.get("answer")
        attempts = game.get("attempts")
        guesses = game.get("guesses")
        if (
            not isinstance(answer, str)
            or isinstance(attempts, bool)
            or not isinstance(attempts, int)
            or attempts <= 0
        ):
            raise ValueError(f"Invalid answer or attempt count in {path}.")
        if answer in attempts_by_answer:
            raise ValueError(f"Duplicate answer {answer!r} in {path}.")
        attempts_by_answer[answer] = attempts

        if guesses is None:
            if game_results.get("format_version") == 2:
                raise ValueError(f"Missing guess sequence for {answer!r} in {path}.")
            continue
        if not isinstance(guesses, list) or len(guesses) != attempts:
            raise ValueError(f"Invalid guess sequence for {answer!r} in {path}.")
        normalized_guesses: list[dict[str, str]] = []
        for step in guesses:
            if (
                not isinstance(step, dict)
                or not isinstance(step.get("guess"), str)
                or not isinstance(step.get("feedback"), str)
                or len(step["feedback"]) != 5
                or set(step["feedback"]) - {"P", "A", "V"}
            ):
                raise ValueError(f"Invalid guess step for {answer!r} in {path}.")
            normalized_guesses.append(
                {"guess": step["guess"], "feedback": step["feedback"]}
            )
        if (
            normalized_guesses[-1]["guess"] != answer
            or normalized_guesses[-1]["feedback"] != "VVVVV"
        ):
            raise ValueError(f"Guess sequence does not solve {answer!r} in {path}.")
        guess_histories[answer] = normalized_guesses
    return attempts_by_answer, guess_histories


def _save_evaluation_json(
    path: Path,
    strategy: Strategy,
    evaluation_key: str,
    word_key: str,
    selected_answers: list[str],
    attempts_by_answer: dict[str, int],
    guess_histories: dict[str, list[dict[str, str]]],
    complete: bool,
    summary: dict[str, int | float | dict[str, int]] | None = None,
) -> Path:
    game_results = {
        "format_version": 2,
        "strategy": strategy,
        "word_list_key": word_key,
        "evaluation_key": evaluation_key,
        "search_settings": _search_settings(),
        "complete": complete,
        "completed_games": len(guess_histories),
        "total_games": len(selected_answers),
        "games": [
            {
                "answer": answer,
                "attempts": attempts_by_answer[answer],
                "guesses": guess_histories[answer],
            }
            for answer in selected_answers
            if answer in attempts_by_answer and answer in guess_histories
        ],
    }
    if summary is not None:
        game_results["summary"] = summary

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as json_file:
            temporary_path = Path(json_file.name)
            json.dump(game_results, json_file, ensure_ascii=False, indent=2)
            json_file.write("\n")
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
    return path


def evaluate_solver(
    strategy: Strategy = "entropy",
    answers: Sequence[str] | None = None,
    resume: bool = True,
    checkpoint_interval: int = 100,
    workers: int = 1,
    answer_list: AnswerList = "accepted",
) -> SolverEvaluation:
    """Evaluate answers with resumable results and optional CPU processes."""
    strategy = _validate_strategy(strategy)
    if checkpoint_interval <= 0:
        raise ValueError("checkpoint_interval must be greater than zero.")
    if workers <= 0:
        raise ValueError("workers must be greater than zero.")
    all_answers = _load_answers(answer_list)
    selected_answers = (
        all_answers
        if answers is None
        else _normalize_candidates(list(answers))
    )
    if not selected_answers:
        raise ValueError("answers must not be empty.")
    invalid_answers = set(selected_answers) - set(all_answers)
    if invalid_answers:
        raise ValueError(
            f"Evaluation answers must be in the selected {answer_list} list: "
            + ", ".join(sorted(invalid_answers))
        )

    run_id = uuid.uuid4().hex[:12]
    runtime_log_path = partition_functions.DATASET_PATH.with_name(
        "entropy_runtime.log"
    )
    run_started = perf_counter()
    _append_runtime_log(
        runtime_log_path,
        run_id,
        "run_started",
        strategy=strategy,
        answer_list=answer_list,
        answer_count=len(selected_answers),
        workers=workers,
        max_k=helpers.MAX_K,
        checkpoint_interval=checkpoint_interval,
        resume=resume,
    )
    print(
        "Preparando a matriz de feedback e o contexto da avaliação.",
        flush=True,
    )
    _append_runtime_log(
        runtime_log_path,
        run_id,
        "feedback_matrix_preparation_started",
        answer_count=len(all_answers),
    )
    try:
        context = _search_context(all_answers)
    except Exception as error:
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "feedback_matrix_preparation_failed",
            error_type=type(error).__name__,
            error=str(error),
        )
        raise
    _append_runtime_log(
        runtime_log_path,
        run_id,
        "feedback_matrix_preparation_completed",
        elapsed_seconds=round(perf_counter() - run_started, 3),
    )
    evaluation_key = helpers.evaluation_scope_key(selected_answers)
    json_output_path = _evaluation_json_path(
        strategy,
        evaluation_key,
        context[3],
    )
    attempts_by_answer = (
        helpers.load_evaluation_results(strategy, evaluation_key)
        if resume
        else {}
    )
    saved_attempts, guess_histories = (
        _load_evaluation_json(
            json_output_path,
            strategy,
            evaluation_key,
            context[3],
        )
        if resume
        else ({}, {})
    )
    for answer, attempts in saved_attempts.items():
        if answer not in selected_answers:
            raise RuntimeError("The saved game JSON contains an unexpected answer.")
        if answer in attempts_by_answer and attempts_by_answer[answer] != attempts:
            raise RuntimeError(
                f"Saved attempt counts disagree for answer {answer!r}."
            )
        attempts_by_answer.setdefault(answer, attempts)
    for answer, guess_history in guess_histories.items():
        if len(guess_history) != attempts_by_answer[answer]:
            raise RuntimeError(
                f"Saved guess sequence disagrees with the attempt count for {answer!r}."
            )
        answer_index = context[1][answer]
        for step in guess_history:
            guess_index = context[1].get(step["guess"])
            if guess_index is None:
                raise RuntimeError(
                    f"Saved guess {step['guess']!r} is not in the vocabulary."
                )
            actual_feedback = _feedback_text(
                int(context[2][guess_index, answer_index])
            )
            if step["feedback"] != actual_feedback:
                raise RuntimeError(
                    f"Saved feedback for {answer!r} does not match that answer."
                )
    if (
        not set(attempts_by_answer).issubset(selected_answers)
        or any(attempts <= 0 for attempts in attempts_by_answer.values())
    ):
        raise RuntimeError("The persisted evaluation checkpoint is invalid.")
    if not resume:
        helpers.clear_evaluation_results(strategy, evaluation_key)
        guess_histories.clear()

    pending_answers = [
        answer
        for answer in selected_answers
        if answer not in guess_histories
    ]
    _append_runtime_log(
        runtime_log_path,
        run_id,
        "saved_results_loaded",
        completed_answers=len(guess_histories),
        pending_answers=len(pending_answers),
    )
    pending_results: dict[str, int] = {}
    initial_guess_index: int | None = None
    if pending_answers and strategy == "deep":
        if helpers._PROFILE is not None:
            helpers._PROFILE.worker_processes = min(workers, len(all_answers))
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "initial_groups_search_started",
            max_k=helpers.MAX_K,
        )
        try:
            initial_guess_index = choose_first_guess(
                workers=workers,
                answer_list=answer_list,
            )[0]
        except Exception as error:
            _append_runtime_log(
                runtime_log_path,
                run_id,
                "initial_groups_search_failed",
                error_type=type(error).__name__,
                error=str(error),
            )
            raise
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "initial_groups_search_completed",
            guess=context[0][initial_guess_index],
        )

    worker_count = min(workers, len(pending_answers)) if pending_answers else 0
    if helpers._PROFILE is not None:
        helpers._PROFILE.worker_processes = max(
            helpers._PROFILE.worker_processes,
            worker_count,
        )

    _save_evaluation_json(
        json_output_path,
        strategy,
        evaluation_key,
        context[3],
        selected_answers,
        attempts_by_answer,
        guess_histories,
        complete=False,
    )

    if worker_count <= 1:
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "serial_answer_evaluation_started",
            pending_answers=len(pending_answers),
        )
        completed_batches = (
            [
                (
                    answer,
                    *_simulate_and_capture_game(
                        answer,
                        all_answers,
                        strategy,
                        context,
                        initial_guess_index,
                    ),
                )
                for answer in pending_answers[index:index + checkpoint_interval]
            ]
            for index in range(0, len(pending_answers), checkpoint_interval)
        )
        for batch_results in completed_batches:
            for answer, attempts, guess_history in batch_results:
                if attempts <= 0:
                    raise RuntimeError(
                        "simulate_game returned a non-positive attempt count."
                    )
                attempts_by_answer[answer] = attempts
                guess_histories[answer] = guess_history
                pending_results[answer] = attempts
            helpers.save_evaluation_results(
                strategy,
                evaluation_key,
                pending_results,
            )
            pending_results.clear()
            _save_evaluation_json(
                json_output_path,
                strategy,
                evaluation_key,
                context[3],
                selected_answers,
                attempts_by_answer,
                guess_histories,
                complete=False,
            )
            print(
                f"Respostas avaliadas: {len(attempts_by_answer)}/"
                f"{len(selected_answers)}"
            )
            _append_runtime_log(
                runtime_log_path,
                run_id,
                "answer_checkpoint_saved",
                completed_answers=len(attempts_by_answer),
                total_answers=len(selected_answers),
            )
    elif pending_answers:
        worker_memo_base = partition_functions.DATASET_PATH.with_name(
            "entropy_memo_worker.sqlite3"
        )
        batch_size = max(1, checkpoint_interval // worker_count)
        batches = [
            pending_answers[index:index + batch_size]
            for index in range(0, len(pending_answers), batch_size)
        ]
        completed_count = 0
        evaluation_started = perf_counter()
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "parallel_answer_evaluation_started",
            worker_count=worker_count,
            batch_count=len(batches),
            batch_size=batch_size,
        )
        with ProcessPoolExecutor(
            max_workers=worker_count,
            mp_context=multiprocessing.get_context("spawn"),
            initializer=_initialize_evaluation_worker,
            initargs=(
                all_answers,
                strategy,
                partition_functions.DATASET_PATH,
                worker_memo_base,
                worker_count,
                initial_guess_index,
                helpers._PROFILE is not None,
                helpers.MAX_K,
            ),
        ) as executor:
            futures = {
                executor.submit(
                    _process_evaluation_batch,
                    batch,
                    batch_index,
                    runtime_log_path,
                    run_id,
                ): batch_index
                for batch_index, batch in enumerate(batches)
            }
            ready_batches: dict[
                int,
                tuple[
                    list[tuple[str, int, list[dict[str, str]]]],
                    helpers.SearchProfile | None,
                ],
            ] = {}
            next_batch_to_commit = 0
            completed_batch_count = 0
            while futures:
                finished_futures, _ = wait(
                    futures,
                    timeout=_RUN_LOG_HEARTBEAT_SECONDS,
                    return_when=FIRST_COMPLETED,
                )
                if not finished_futures:
                    _append_runtime_log(
                        runtime_log_path,
                        run_id,
                        "parallel_evaluation_heartbeat",
                        completed_batches=completed_batch_count,
                        batch_count=len(batches),
                        committed_batches=next_batch_to_commit,
                        completed_answers=len(attempts_by_answer),
                        elapsed_seconds=round(
                            perf_counter() - evaluation_started,
                            3,
                        ),
                    )
                    continue

                for future in finished_futures:
                    batch_index = futures.pop(future)
                    try:
                        batch_result = future.result()
                    except Exception as error:
                        _append_runtime_log(
                            runtime_log_path,
                            run_id,
                            "parallel_evaluation_batch_failed",
                            batch_index=batch_index,
                            error_type=type(error).__name__,
                            error=str(error),
                        )
                        raise
                    ready_batches[batch_index] = batch_result
                    completed_batch_count += 1
                    _append_runtime_log(
                        runtime_log_path,
                        run_id,
                        "parallel_evaluation_batch_completed",
                        batch_index=batch_index,
                        completed_batches=completed_batch_count,
                        batch_count=len(batches),
                        answers_in_batch=len(batch_result[0]),
                        elapsed_seconds=round(
                            perf_counter() - evaluation_started,
                            3,
                        ),
                    )

                while next_batch_to_commit in ready_batches:
                    batch_results, worker_profile = ready_batches.pop(
                        next_batch_to_commit
                    )
                    next_batch_to_commit += 1
                    if helpers._PROFILE is not None and worker_profile is not None:
                        _merge_worker_profile(helpers._PROFILE, worker_profile)
                    for answer, attempts, guess_history in batch_results:
                        if attempts <= 0:
                            raise RuntimeError(
                                "simulate_game returned a non-positive attempt count."
                            )
                        attempts_by_answer[answer] = attempts
                        guess_histories[answer] = guess_history
                        pending_results[answer] = attempts
                    helpers.save_evaluation_results(
                        strategy,
                        evaluation_key,
                        pending_results,
                    )
                    completed_count += len(pending_results)
                    pending_results.clear()
                    _save_evaluation_json(
                        json_output_path,
                        strategy,
                        evaluation_key,
                        context[3],
                        selected_answers,
                        attempts_by_answer,
                        guess_histories,
                        complete=False,
                    )
                    if (
                        completed_count % checkpoint_interval == 0
                        or completed_count == len(pending_answers)
                    ):
                        print(
                            f"Respostas avaliadas: {len(attempts_by_answer)}/"
                            f"{len(selected_answers)}"
                        )
                    _append_runtime_log(
                        runtime_log_path,
                        run_id,
                        "answer_checkpoint_saved",
                        completed_answers=len(attempts_by_answer),
                        total_answers=len(selected_answers),
                        committed_batches=next_batch_to_commit,
                    )
        _append_runtime_log(
            runtime_log_path,
            run_id,
            "parallel_answer_evaluation_completed",
            completed_batches=completed_batch_count,
            batch_count=len(batches),
            completed_answers=len(attempts_by_answer),
            elapsed_seconds=round(
                perf_counter() - evaluation_started,
                3,
            ),
        )

    if (
        len(attempts_by_answer) != len(selected_answers)
        or len(guess_histories) != len(selected_answers)
    ):
        raise RuntimeError("The evaluation checkpoint is incomplete.")

    ordered_attempts = {
        answer: attempts_by_answer[answer]
        for answer in selected_answers
    }
    distribution = dict(sorted(Counter(ordered_attempts.values()).items()))
    worst_case = max(ordered_attempts.values())
    worst_answers = tuple(
        answer
        for answer, attempts in ordered_attempts.items()
        if attempts == worst_case
    )
    wins_up_to_six = sum(
        attempts <= 6 for attempts in ordered_attempts.values()
    )
    json_output_path = _save_evaluation_json(
        json_output_path,
        strategy,
        evaluation_key,
        context[3],
        selected_answers,
        ordered_attempts,
        guess_histories,
        complete=True,
        summary={
            "average_attempts": sum(ordered_attempts.values()) / len(selected_answers),
            "worst_case": worst_case,
            "win_rate_up_to_six": wins_up_to_six / len(selected_answers),
            "distribution": {
                str(attempts): count
                for attempts, count in distribution.items()
            },
        },
    )
    print(f"Jogos salvos em: {json_output_path}")
    _append_runtime_log(
        runtime_log_path,
        run_id,
        "run_completed",
        total_games=len(selected_answers),
        average_attempts=sum(ordered_attempts.values()) / len(selected_answers),
        worst_case=worst_case,
        output_json=str(json_output_path),
        elapsed_seconds=round(perf_counter() - run_started, 3),
    )
    return SolverEvaluation(
        average_attempts=sum(ordered_attempts.values()) / len(selected_answers),
        worst_case=worst_case,
        worst_answers=worst_answers,
        distribution=distribution,
        win_rate_up_to_six=wins_up_to_six / len(selected_answers),
        total_games=len(selected_answers),
    )


def _print_profile(profile: helpers.SearchProfile) -> None:
    summary = helpers.search_profile_summary(profile)
    print(f"Search profile: {summary}")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Entropy-based Termo solver.")
    commands = parser.add_subparsers(dest="command", required=True)

    play_parser = commands.add_parser("play", help="play interactively")
    play_parser.add_argument(
        "--strategy",
        choices=("entropy", "groups", "deep"),
        default="entropy",
        help="entropy ranks guesses only; groups recursively analyzes feedback groups",
    )
    play_parser.add_argument(
        "--answer-list",
        choices=("accepted", "solutions"),
        default="accepted",
        help=(
            "possible answers: termo_palavras_aceitas or "
            "termo_solucoes_possiveis"
        ),
    )
    play_parser.add_argument(
        "--max-k",
        type=int,
        help="maximum number of guesses ranked at each groups-search state",
    )
    play_parser.add_argument("--profile", action="store_true")

    simulate_parser = commands.add_parser("simulate", help="simulate one answer")
    simulate_parser.add_argument("answer")
    simulate_parser.add_argument(
        "--strategy",
        choices=("entropy", "groups", "deep"),
        default="entropy",
        help="entropy ranks guesses only; groups recursively analyzes feedback groups",
    )
    simulate_parser.add_argument(
        "--answer-list",
        choices=("accepted", "solutions"),
        default="accepted",
        help=(
            "possible answers: termo_palavras_aceitas or "
            "termo_solucoes_possiveis"
        ),
    )
    simulate_parser.add_argument(
        "--max-k",
        type=int,
        help="maximum number of guesses ranked at each groups-search state",
    )
    simulate_parser.add_argument("--profile", action="store_true")

    evaluate_parser = commands.add_parser(
        "evaluate",
        help="evaluate every answer in the selected answer list (may take a long time)",
    )
    evaluate_parser.add_argument(
        "--strategy",
        choices=("entropy", "groups", "deep"),
        default="entropy",
        help="entropy ranks guesses only; groups recursively analyzes feedback groups",
    )
    evaluate_parser.add_argument(
        "--answer-list",
        choices=("accepted", "solutions"),
        default="accepted",
        help=(
            "possible answers: termo_palavras_aceitas or "
            "termo_solucoes_possiveis"
        ),
    )
    evaluate_parser.add_argument(
        "--max-k",
        type=int,
        help="maximum number of guesses ranked at each groups-search state",
    )
    evaluate_parser.add_argument(
        "--sample-size",
        type=int,
        help="evaluate a deterministic random sample instead of every answer",
    )
    evaluate_parser.add_argument("--seed", type=int, default=2026)
    evaluate_parser.add_argument("--checkpoint-interval", type=int, default=100)
    evaluate_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="maximum CPU worker processes for groups search and evaluation",
    )
    evaluate_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="discard saved answer results and evaluate the selected set again",
    )
    evaluate_parser.add_argument("--profile", action="store_true")

    args = parser.parse_args(argv)
    if args.max_k is not None and args.max_k <= 0:
        raise ValueError("--max-k must be greater than zero.")
    if args.max_k is not None and args.strategy == "entropy":
        raise ValueError("--max-k can only be used with the groups strategy.")
    helpers.MAX_K = args.max_k

    if args.command == "play":
        if args.profile:
            with helpers.profile_search() as profile:
                interactive_play(args.strategy, args.answer_list)
            _print_profile(profile)
        else:
            interactive_play(args.strategy, args.answer_list)
    elif args.command == "simulate":
        if args.profile:
            with helpers.profile_search() as profile:
                attempts = simulate_game(
                    args.answer,
                    args.strategy,
                    args.answer_list,
                )
            _print_profile(profile)
        else:
            attempts = simulate_game(
                args.answer,
                args.strategy,
                args.answer_list,
            )
        print(f"{args.answer.strip().upper()}: {attempts} guesses")
    else:
        if args.sample_size is not None:
            if args.sample_size <= 0:
                raise ValueError("--sample-size must be greater than zero.")
            all_answers = _load_answers(args.answer_list)
            if args.sample_size > len(all_answers):
                raise ValueError(
                    f"--sample-size cannot exceed {len(all_answers)} answers."
                )
            evaluation_answers = random.Random(args.seed).sample(
                all_answers,
                args.sample_size,
            )
        else:
            evaluation_answers = None

        if args.profile:
            with helpers.profile_search() as profile:
                result = evaluate_solver(
                    args.strategy,
                    answers=evaluation_answers,
                    resume=not args.no_resume,
                    checkpoint_interval=args.checkpoint_interval,
                    workers=args.workers,
                    answer_list=args.answer_list,
                )
            _print_profile(profile)
        else:
            result = evaluate_solver(
                args.strategy,
                answers=evaluation_answers,
                resume=not args.no_resume,
                checkpoint_interval=args.checkpoint_interval,
                workers=args.workers,
                answer_list=args.answer_list,
            )
        print(f"Games: {result.total_games}")
        print(f"Average guesses: {result.average_attempts:.3f}")
        print(f"Worst case: {result.worst_case}")
        print(f"Worst-case answers: {', '.join(result.worst_answers)}")
        print(f"Distribution: {result.distribution}")
        print(f"Win rate in 6 guesses: {result.win_rate_up_to_six:.2%}")


if __name__ == "__main__":
    main()
