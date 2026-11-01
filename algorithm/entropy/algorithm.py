"""Solver orchestration and command-line interface for Termo."""

import argparse
from collections import Counter, OrderedDict
from collections.abc import Callable, Sequence
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile
from typing import Literal, NamedTuple, Sequence

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


def _search_context(candidates: list[str]) -> _SearchContext:
    guesses = _load_answers()
    for candidate in candidates:
        normalized_candidate = candidate.strip().upper()
        if normalized_candidate not in guesses:
            guesses.append(normalized_candidate)
    matrix, word_indices, word_key = partition_functions._get_feedback_matrix(
        guesses
    )
    helpers.configure_memo_store(
        partition_functions.DATASET_PATH.with_name("entropy_memo.sqlite3"),
        word_key,
    )
    return guesses, word_indices, matrix, word_key


def best_move(candidates: list[str], depth: int = 0) -> tuple[int, float]:
    """Return the best guess index and expected number of guesses."""
    if depth < 0:
        raise ValueError("depth must be non-negative.")
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")
    context = _search_context(normalized_candidates)
    return helpers._best_move(normalized_candidates, depth, context)


def evaluate_guess(i: int, candidates: list[str], limit: float) -> float:
    """Evaluate the expected cost of trying guess index ``i``."""
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")
    context = _search_context(normalized_candidates)
    if i < 0 or i >= len(context[0]):
        raise IndexError("guess index is outside the guess list.")
    return helpers._evaluate_guess(i, normalized_candidates, limit, 0, context)


def choose_first_guess() -> tuple[int, float]:
    """Load or calculate the deep-search first guess and persist its result."""
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

    guess_index, expected_cost = best_move(candidates)
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


def evaluate_solver(
    strategy: Strategy = "entropy",
    answers: Sequence[str] | None = None,
    resume: bool = True,
    checkpoint_interval: int = 100,
) -> SolverEvaluation:
    """Evaluate answers with resumable results and a shared feedback context."""
    strategy = _validate_strategy(strategy)
    if checkpoint_interval <= 0:
        raise ValueError("checkpoint_interval must be greater than zero.")
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

    context = _search_context(all_answers)
    evaluation_key = helpers.evaluation_scope_key(selected_answers)
    attempts_by_answer = (
        helpers.load_evaluation_results(strategy, evaluation_key)
        if resume
        else {}
    )
    if (
        not set(attempts_by_answer).issubset(selected_answers)
        or any(attempts <= 0 for attempts in attempts_by_answer.values())
    ):
        raise RuntimeError("The persisted evaluation checkpoint is invalid.")
    if not resume:
        helpers.clear_evaluation_results(strategy, evaluation_key)

    initial_guess_index: int | None = None
    if strategy == "deep":
        initial_guess_index = choose_first_guess()[0]

    pending_results: dict[str, int] = {}
    for answer in selected_answers:
        if answer in attempts_by_answer:
            continue
        attempts = _simulate_game_with_context(
            answer,
            all_answers,
            strategy,
            context,
            initial_guess_index,
        )
        if attempts <= 0:
            raise RuntimeError("simulate_game returned a non-positive attempt count.")
        attempts_by_answer[answer] = attempts
        pending_results[answer] = attempts
        if len(pending_results) >= checkpoint_interval:
            helpers.save_evaluation_results(
                strategy,
                evaluation_key,
                pending_results,
            )
            pending_results.clear()
            print(
                f"Respostas avaliadas: {len(attempts_by_answer)}/"
                f"{len(selected_answers)}"
            )
    if pending_results:
        helpers.save_evaluation_results(
            strategy,
            evaluation_key,
            pending_results,
        )

    if len(attempts_by_answer) != len(selected_answers):
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
                )
            _print_profile(profile)
        else:
            result = evaluate_solver(
                args.strategy,
                answers=evaluation_answers,
                resume=not args.no_resume,
                checkpoint_interval=args.checkpoint_interval,
            )
        print(f"Games: {result.total_games}")
        print(f"Average guesses: {result.average_attempts:.3f}")
        print(f"Worst case: {result.worst_case}")
        print(f"Worst-case answers: {', '.join(result.worst_answers)}")
        print(f"Distribution: {result.distribution}")
        print(f"Win rate in 6 guesses: {result.win_rate_up_to_six:.2%}")


if __name__ == "__main__":
    main()
