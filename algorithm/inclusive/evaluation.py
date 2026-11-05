"""Batch evaluation of all answers with the inclusive solver."""

import argparse
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from algorithm import functions as f
from algorithm.inclusive import algorithm as inclusive
from algorithm.inclusive import functions as heuristics

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_DIR / "dataset"
WORD_LIST_PATH = DATASET_DIR / "words" / "termo_palavras_aceitas.txt"
RESULTS_PATH = DATASET_DIR / "results" / "resultados_inclusive.json"

WordFunction = Callable[[list[str]], str]
_WORKER_WORD_LIST: list[str] = []
_WORKER_WORD_FUNCTION: WordFunction | None = None


def _get_word_function(heuristic: str) -> WordFunction:
    if heuristic == "position":
        return heuristics.find_best_word_by_letter_position
    if heuristic == "frequency":
        return heuristics.find_best_word_by_letter_frequency
    raise ValueError(f"Heurística inclusiva desconhecida: {heuristic}")


def _initialize_worker(word_list: list[str], heuristic: str) -> None:
    global _WORKER_WORD_LIST, _WORKER_WORD_FUNCTION
    _WORKER_WORD_LIST = word_list
    _WORKER_WORD_FUNCTION = _get_word_function(heuristic)


def _process_answer(answer: str) -> dict[str, object]:
    if _WORKER_WORD_FUNCTION is None:
        raise RuntimeError("A heurística do worker inclusivo não foi inicializada.")
    guesses: list[dict[str, str]] = []

    def record_guess(guess: str, feedback: f.Feedback) -> None:
        guesses.append(
            {"guess": guess, "feedback": f.feedback_to_text(feedback)}
        )

    try:
        attempts = inclusive.inclusive_algorithm(
            _WORKER_WORD_LIST.copy(),
            answer,
            _WORKER_WORD_FUNCTION,
            show_progress=False,
            on_guess=record_guess,
        )
    except (RuntimeError, AssertionError, ValueError):
        return {
            "answer": answer,
            "attempts": -1,
            "solved": False,
            "guesses": guesses,
        }
    return {
        "answer": answer,
        "attempts": attempts,
        "solved": True,
        "guesses": guesses,
    }


def run_all_answers(
    word_list: list[str],
    output_path: Path,
    heuristic: str = "position",
    max_workers: int = 1,
) -> tuple[int, int]:
    if max_workers <= 0:
        raise ValueError("max_workers deve ser maior que zero.")
    _get_word_function(heuristic)
    games: list[dict[str, object]] = []
    payload: dict[str, object] = {
        "format_version": 1,
        "algorithm": "inclusive",
        "word_list_key": f.word_list_key(word_list),
        "settings": {"heuristic": heuristic},
        "complete": False,
        "completed_games": 0,
        "total_games": len(word_list),
        "games": games,
    }
    f.write_json_checkpoint(output_path, payload)
    if not word_list:
        payload["complete"] = True
        payload["summary"] = f.summarize_evaluation_games(games)
        f.write_json_checkpoint(output_path, payload)
        return 0, 0

    worker_count = min(max_workers, len(word_list))
    batch_size = 25
    _initialize_worker(word_list, heuristic)
    if worker_count == 1:
        results = map(_process_answer, word_list)
        executor_context = None
    else:
        executor_context = ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=_initialize_worker,
            initargs=(word_list, heuristic),
        )
        results = executor_context.map(_process_answer, word_list)

    try:
        for game in results:
            games.append(game)
            payload["completed_games"] = len(games)
            if len(games) % batch_size == 0 or len(games) == len(word_list):
                f.write_json_checkpoint(output_path, payload)
                print(f"Respostas processadas: {len(games)}/{len(word_list)}")
    finally:
        if executor_context is not None:
            executor_context.shutdown()

    payload["complete"] = True
    payload["summary"] = f.summarize_evaluation_games(games)
    f.write_json_checkpoint(output_path, payload)
    return len(word_list), len(word_list)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Avaliar todas as respostas com o algoritmo inclusivo."
    )
    parser.add_argument(
        "--heuristic",
        choices=("position", "frequency"),
        default="position",
        help="heurística de escolha de palpite (padrão: position)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="processos paralelos (padrão: 1)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_PATH,
        help="caminho do JSON de resultados",
    )
    args = parser.parse_args(argv)

    word_list = f.file_to_list(str(WORD_LIST_PATH))
    answers_processed, simulations = run_all_answers(
        word_list,
        args.output,
        heuristic=args.heuristic,
        max_workers=args.workers,
    )
    print(f"Simulações concluídas: {simulations} para {answers_processed} respostas.")
    print(f"Resultados salvos em: {args.output}")


if __name__ == "__main__":
    main()
