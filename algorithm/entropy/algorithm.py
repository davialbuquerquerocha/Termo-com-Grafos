"""Solver orchestration and command-line interface for Termo."""

import argparse
from collections import Counter
from collections.abc import Callable, Sequence
import hashlib
import json
import math
from pathlib import Path
import tempfile
from typing import Literal, NamedTuple

import numpy as np

from algorithm.partition import functions as partition_functions
from . import functions as helpers

Strategy = Literal["entropy", "deep"]
GuessSelector = Callable[[list[str]], int]

_ENTROPY_GUESS_CACHE: dict[
    tuple[str, int, int, tuple[str, ...]], int
] = {}
_SEARCH_ALGORITHM_VERSION = 2

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
    if strategy == "deep":
        return "deep"
    raise ValueError("strategy must be either 'entropy' or 'deep'.")


def _search_settings() -> dict[str, int | float]:
    return {
        "algorithm_version": _SEARCH_ALGORITHM_VERSION,
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
    """Select a guess using pure entropy ranking or deep search."""
    strategy = _validate_strategy(strategy)
    normalized_candidates = _normalize_candidates(candidates)
    if not normalized_candidates:
        raise ValueError("candidates must not be empty.")

    if strategy == "deep":
        return best_move(normalized_candidates, depth)[0]

    word_list_path = partition_functions.DATASET_PATH
    word_list_stat = word_list_path.stat()
    cache_key = (
        str(word_list_path),
        word_list_stat.st_mtime_ns,
        word_list_stat.st_size,
        tuple(normalized_candidates),
    )
    cached_guess = _ENTROPY_GUESS_CACHE.get(cache_key)
    if cached_guess is not None:
        return cached_guess

    ranked_guesses = helpers.ranking(normalized_candidates, 1)
    guess_index = (
        ranked_guesses[-1]
        if len(normalized_candidates) == 1
        else ranked_guesses[0]
    )
    _ENTROPY_GUESS_CACHE[cache_key] = guess_index
    return guess_index


def _expected_cost(
    guess_index: int,
    candidates: list[str],
    strategy: Strategy,
    depth: int = 0,
) -> float:
    if strategy == "deep":
        return best_move(candidates, depth)[1]
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
    """Play interactively using the selected guess strategy."""
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
                guess_index, expected_cost = best_move(candidates, depth)
            else:
                guess_index = choose_guess(candidates, strategy)
                expected_cost = _expected_cost(
                    guess_index,
                    candidates,
                    strategy,
                    depth,
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
    """Simulate a game against a known answer and return guesses used."""
    strategy = _validate_strategy(strategy)
    normalized_answer = answer.strip().upper()
    candidates = _load_answers()
    if normalized_answer not in candidates:
        raise ValueError(
            f"The answer {normalized_answer!r} is not in the accepted-word list."
        )

    context = _search_context(candidates)
    guesses, word_indices, matrix, _ = context
    winning_feedback = partition_functions._FEEDBACK_PATTERN_COUNT - 1
    answer_index = word_indices[normalized_answer]
    initial_deep_guess = choose_first_guess() if strategy == "deep" else None
    guess_index = (
        initial_deep_guess[0]
        if initial_deep_guess is not None
        else choose_guess(candidates, strategy)
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
        guess_index = choose_guess(candidates, strategy, attempts)


def evaluate_solver(strategy: Strategy = "entropy") -> SolverEvaluation:
    """Evaluate every accepted answer and return aggregate solver statistics."""
    strategy = _validate_strategy(strategy)
    answers = _load_answers()
    attempts_by_answer = {
        answer: simulate_game(answer, strategy)
        for answer in answers
    }
    if any(attempts <= 0 for attempts in attempts_by_answer.values()):
        raise RuntimeError("simulate_game returned a non-positive attempt count.")

    distribution = dict(sorted(Counter(attempts_by_answer.values()).items()))
    worst_case = max(attempts_by_answer.values())
    worst_answers = tuple(
        answer
        for answer, attempts in attempts_by_answer.items()
        if attempts == worst_case
    )
    wins_up_to_six = sum(
        attempts <= 6 for attempts in attempts_by_answer.values()
    )
    return SolverEvaluation(
        average_attempts=sum(attempts_by_answer.values()) / len(answers),
        worst_case=worst_case,
        worst_answers=worst_answers,
        distribution=distribution,
        win_rate_up_to_six=wins_up_to_six / len(answers),
        total_games=len(answers),
    )


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Entropy-based Termo solver.")
    commands = parser.add_subparsers(dest="command", required=True)

    play_parser = commands.add_parser("play", help="play interactively")
    play_parser.add_argument(
        "--strategy",
        choices=("entropy", "deep"),
        default="entropy",
    )

    simulate_parser = commands.add_parser("simulate", help="simulate one answer")
    simulate_parser.add_argument("answer")
    simulate_parser.add_argument(
        "--strategy",
        choices=("entropy", "deep"),
        default="entropy",
    )

    evaluate_parser = commands.add_parser(
        "evaluate",
        help="evaluate every accepted answer (may take a long time)",
    )
    evaluate_parser.add_argument(
        "--strategy",
        choices=("entropy", "deep"),
        default="entropy",
    )

    args = parser.parse_args(argv)
    if args.command == "play":
        interactive_play(args.strategy)
    elif args.command == "simulate":
        print(
            f"{args.answer.strip().upper()}: "
            f"{simulate_game(args.answer, args.strategy)} guesses"
        )
    else:
        result = evaluate_solver(args.strategy)
        print(f"Games: {result.total_games}")
        print(f"Average guesses: {result.average_attempts:.3f}")
        print(f"Worst case: {result.worst_case}")
        print(f"Worst-case answers: {', '.join(result.worst_answers)}")
        print(f"Distribution: {result.distribution}")
        print(f"Win rate in 6 guesses: {result.win_rate_up_to_six:.2%}")


if __name__ == "__main__":
    main()
