"""Solver orchestration and command-line interface for Termo."""

import argparse
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import contextmanager
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import random
import re
import tempfile
from threading import Event, Thread
from time import perf_counter
from typing import Generator, Literal, NamedTuple

import numpy as np

from algorithm.partition import functions as partition_functions
from . import functions as helpers

Strategy = Literal["entropy", "groups", "deep"]
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


class SolverEvaluation(NamedTuple):
    average_attempts: float
    worst_case: int
    worst_answers: tuple[str, ...]
    distribution: dict[int, int]
    win_rate_up_to_six: float
    total_games: int


__all__ = [
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


def _validate_strategy(strategy: str) -> Strategy:
    if strategy == "entropy":
        return "entropy"
    if strategy in ("groups", "deep"):
        return "deep"
    raise ValueError(
        "strategy must be 'entropy' for entropy-only selection or "
        "'groups' to recursively analyze feedback groups."
    )


@contextmanager
def _progress_heartbeat(
    status: Callable[[], str],
    interval_seconds: float = 10.0,
) -> Generator[None, None, None]:
    stop_event = Event()
    started = perf_counter()

    def report_progress() -> None:
        while not stop_event.wait(interval_seconds):
            elapsed = perf_counter() - started
            print(
                f"{status()} (tempo decorrido: {elapsed:.0f}s)",
                flush=True,
            )

    reporter = Thread(target=report_progress, daemon=True)
    reporter.start()
    try:
        yield
    finally:
        stop_event.set()
        reporter.join()


def _search_settings() -> dict[str, int | float]:
    return {
        "algorithm_version": helpers.SEARCH_ALGORITHM_VERSION,
        "exhaustive_limit": helpers.EXHAUSTIVE_LIMIT,
        "budget": helpers.BUDGET,
        "factor": helpers.FACTOR,
        "min_k": helpers.MIN_K,
        "entropy_margin": helpers.ENTROPY_MARGIN,
    }


def _normalize_candidates(candidates: list[str]) -> list[str]:
    return list(
        dict.fromkeys(candidate.strip().upper() for candidate in candidates)
    )


def _load_answers() -> list[str]:
    with partition_functions.DATASET_PATH.open(encoding="utf-8") as word_file:
        answers = _normalize_candidates(word_file.readlines())
    if not answers:
        raise ValueError("The accepted-word list must not be empty.")
    return answers


def _search_context(
    candidates: list[str],
    memo_path: Path | None = None,
) -> _SearchContext:
    guesses = _load_answers()
    for candidate in candidates:
        normalized_candidate = candidate.strip().upper()
        if normalized_candidate not in guesses:
            guesses.append(normalized_candidate)
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
        return helpers._best_move(normalized_candidates, depth, context)
    return helpers._best_move(
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


def evaluate_guess(i: int, candidates: list[str], limit: float) -> float:
    """Evaluate the expected cost of trying guess index ``i``."""
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")
    context = _search_context(normalized_candidates)
    if i < 0 or i >= len(context[0]):
        raise IndexError("guess index is outside the guess list.")
    return helpers._evaluate_guess(i, normalized_candidates, limit, 0, context)


def choose_first_guess(workers: int = 1) -> tuple[int, float]:
    """Load or calculate the deep-search first guess and persist its result."""
    if workers <= 0:
        raise ValueError("workers must be greater than zero.")
    word_list_path = partition_functions.DATASET_PATH
    word_list_content = word_list_path.read_bytes()
    word_list_hash = hashlib.sha256(word_list_content).hexdigest()
    candidates = _normalize_candidates(
        word_list_content.decode("utf-8").splitlines()
    )
    if not candidates:
        raise ValueError("The accepted-word list must not be empty.")

    cache_path = word_list_path.with_name("entropy_first_guess.json")
    if cache_path.exists():
        cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(cached_data, dict):
            raise ValueError(f"Invalid first-guess cache format in {cache_path}.")
        if cached_data.get("word_list_hash") == word_list_hash:
            if cached_data.get("search_settings") != _search_settings():
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
                return candidates.index(guess), float(expected_cost)
            except ValueError as error:
                raise ValueError(
                    f"Cached first guess {guess!r} is absent from {word_list_path}."
                ) from error

    print(
        "Calculando o primeiro palpite de groups; "
        "a busca inicial pode ser demorada.",
        flush=True,
    )
    with _progress_heartbeat(
        lambda: "Busca inicial do primeiro palpite ainda em andamento."
    ):
        guess_index, expected_cost = best_move(candidates, workers=workers)
    if not 0 <= guess_index < len(candidates):
        raise RuntimeError("best_move returned an index outside the word list.")
    if not math.isfinite(expected_cost) or expected_cost <= 0:
        raise RuntimeError("best_move returned an invalid expected cost.")

    cache_data = {
        "word_list_hash": word_list_hash,
        "search_settings": _search_settings(),
        "guess": candidates[guess_index],
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
        return helpers._best_move(candidates, depth, context)[0]

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


def interactive_play(strategy: Strategy = "entropy") -> str:
    """Play using entropy only or recursively analyzed feedback groups."""
    strategy = _validate_strategy(strategy)
    candidates = _load_answers()
    context = _search_context(candidates)
    guesses, word_indices, matrix, _ = context
    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    initial_deep_guess = choose_first_guess() if strategy == "deep" else None
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


def simulate_game(answer: str, strategy: Strategy = "entropy") -> int:
    """Simulate a game with entropy-only or feedback-group analysis."""
    strategy = _validate_strategy(strategy)
    normalized_answer = answer.strip().upper()
    candidates = _load_answers()
    if normalized_answer not in candidates:
        raise ValueError(
            f"The answer {normalized_answer!r} is not in the accepted-word list."
        )

    context = _search_context(candidates)
    initial_deep_guess = choose_first_guess() if strategy == "deep" else None
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
) -> None:
    global _WORKER_ANSWERS, _WORKER_STRATEGY, _WORKER_CONTEXT
    global _WORKER_MEMO_PATH, _WORKER_INITIAL_GUESS_INDEX, _WORKER_PROFILE
    global _WORKER_ROOT_CANDIDATES, _WORKER_ROOT_DEPTH
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
    _WORKER_CONTEXT = _search_context(all_answers, worker_memo_path)


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
        if _WORKER_PROFILE:
            with helpers.profile_search() as profile:
                for guess_index, limit in guesses:
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
    search_started = perf_counter()
    started = perf_counter()
    print(
        f"Busca inicial: avaliando palpite base 1/{len(ranked_guesses)}.",
        flush=True,
    )
    with _progress_heartbeat(
        lambda: "Busca inicial ainda calculando o palpite base 1/"
        f"{len(ranked_guesses)}."
    ):
        best_cost = helpers._evaluate_guess(
            first_guess,
            candidates,
            best_cost,
            depth,
            context,
        )
    if helpers._PROFILE is not None:
        helpers._PROFILE.guess_evaluations += 1
        helpers._PROFILE.evaluation_seconds += perf_counter() - started
    if math.isfinite(best_cost):
        best_guess = first_guess

    remaining_guesses = ranked_guesses[1:]
    if not remaining_guesses:
        return best_guess, best_cost
    completed_guesses = 1
    progress_interval = max(1, len(ranked_guesses) // 100)
    next_progress_report = progress_interval
    print(
        f"Busca inicial: palpite base concluído; "
        f"avaliando os outros {len(remaining_guesses)} em paralelo.",
        flush=True,
    )

    worker_count = min(workers, len(remaining_guesses))
    if helpers._PROFILE is not None:
        helpers._PROFILE.worker_processes = max(
            helpers._PROFILE.worker_processes,
            worker_count,
        )
    memo_base = partition_functions.DATASET_PATH.with_name(
        "entropy_memo_worker.sqlite3"
    )
    batch_size = 8
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
        ),
    ) as executor:
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
                executor.submit(_process_root_guess_batch, task): len(task)
                for task in tasks
            }
            while futures:
                completed, _ = wait(
                    futures,
                    timeout=10.0,
                    return_when=FIRST_COMPLETED,
                )
                if not completed:
                    elapsed = perf_counter() - search_started
                    print(
                        f"Busca inicial: {completed_guesses}/"
                        f"{len(ranked_guesses)} palpites concluídos; "
                        f"em andamento nos workers "
                        f"({elapsed:.0f}s decorridos).",
                        flush=True,
                    )
                    continue
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
                    completed_guesses += futures.pop(future)
                    if (
                        completed_guesses >= next_progress_report
                        or completed_guesses == len(ranked_guesses)
                    ):
                        while next_progress_report <= completed_guesses:
                            next_progress_report += progress_interval
                        elapsed = perf_counter() - search_started
                        print(
                            f"Busca inicial: {completed_guesses}/"
                            f"{len(ranked_guesses)} palpites concluídos "
                            f"({elapsed:.0f}s).",
                            flush=True,
                        )
    return best_guess, best_cost


def _process_evaluation_batch(
    answers: list[str],
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
    try:
        if _WORKER_PROFILE:
            with helpers.profile_search() as profile:
                for answer in answers:
                    attempts, guess_history = _simulate_and_capture_game(
                        answer,
                        _WORKER_ANSWERS,
                        _WORKER_STRATEGY,
                        _WORKER_CONTEXT,
                        _WORKER_INITIAL_GUESS_INDEX,
                    )
                    results.append((answer, attempts, guess_history))
            return results, profile

        for answer in answers:
            attempts, guess_history = _simulate_and_capture_game(
                answer,
                _WORKER_ANSWERS,
                _WORKER_STRATEGY,
                _WORKER_CONTEXT,
                _WORKER_INITIAL_GUESS_INDEX,
            )
            results.append((answer, attempts, guess_history))
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
) -> SolverEvaluation:
    """Evaluate answers with resumable results and optional CPU processes."""
    strategy = _validate_strategy(strategy)
    if checkpoint_interval <= 0:
        raise ValueError("checkpoint_interval must be greater than zero.")
    if workers <= 0:
        raise ValueError("workers must be greater than zero.")
    all_answers = _load_answers()
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
            "Evaluation answers must be in the accepted-word list: "
            + ", ".join(sorted(invalid_answers))
        )

    print(
        "Preparando a matriz de feedback e o contexto da avaliação.",
        flush=True,
    )
    with _progress_heartbeat(
        lambda: "Preparação da matriz de feedback ainda em andamento."
    ):
        context = _search_context(all_answers)
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
    pending_results: dict[str, int] = {}
    initial_guess_index: int | None = None
    if pending_answers and strategy == "deep":
        if helpers._PROFILE is not None:
            helpers._PROFILE.worker_processes = min(workers, len(all_answers))
        initial_guess_index = choose_first_guess(workers=workers)[0]

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
            ),
        ) as executor:
            for batch_results, worker_profile in executor.map(
                _process_evaluation_batch,
                batches,
                chunksize=1,
            ):
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
    play_parser.add_argument("--profile", action="store_true")

    simulate_parser = commands.add_parser("simulate", help="simulate one answer")
    simulate_parser.add_argument("answer")
    simulate_parser.add_argument(
        "--strategy",
        choices=("entropy", "groups", "deep"),
        default="entropy",
        help="entropy ranks guesses only; groups recursively analyzes feedback groups",
    )
    simulate_parser.add_argument("--profile", action="store_true")

    evaluate_parser = commands.add_parser(
        "evaluate",
        help="evaluate every accepted answer (may take a long time)",
    )
    evaluate_parser.add_argument(
        "--strategy",
        choices=("entropy", "groups", "deep"),
        default="entropy",
        help="entropy ranks guesses only; groups recursively analyzes feedback groups",
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
    if args.command == "play":
        if args.profile:
            with helpers.profile_search() as profile:
                interactive_play(args.strategy)
            _print_profile(profile)
        else:
            interactive_play(args.strategy)
    elif args.command == "simulate":
        if args.profile:
            with helpers.profile_search() as profile:
                attempts = simulate_game(args.answer, args.strategy)
            _print_profile(profile)
        else:
            attempts = simulate_game(args.answer, args.strategy)
        print(f"{args.answer.strip().upper()}: {attempts} guesses")
    else:
        if args.sample_size is not None:
            if args.sample_size <= 0:
                raise ValueError("--sample-size must be greater than zero.")
            all_answers = _load_answers()
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
                )
            _print_profile(profile)
        else:
            result = evaluate_solver(
                args.strategy,
                answers=evaluation_answers,
                resume=not args.no_resume,
                checkpoint_interval=args.checkpoint_interval,
                workers=args.workers,
                )
        print(f"Games: {result.total_games}")
        print(f"Average guesses: {result.average_attempts:.3f}")
        print(f"Worst case: {result.worst_case}")
        print(f"Worst-case answers: {', '.join(result.worst_answers)}")
        print(f"Distribution: {result.distribution}")
        print(f"Win rate in 6 guesses: {result.win_rate_up_to_six:.2%}")


if __name__ == "__main__":
    main()
