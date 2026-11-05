"""Batch evaluation of all answers with the partition-based solver."""

import argparse
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path

from algorithm import functions as f
from algorithm.partition import algorithm as partition
from algorithm.partition import functions as partition_functions

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_DIR / "dataset"
WORD_LIST_PATH = DATASET_DIR / "words" / "termo_palavras_aceitas.txt"
PARTITION_RESULTS_PATH = (
    DATASET_DIR / "results" / "resultados_partition_busca_limitada.json"
)

WordFunction = Callable[[list[str]], str]
AlgorithmFunction = Callable[..., int]

_WORKER_WORD_LIST: list[str] = []


def _initialize_worker(
    word_list: list[str],
    bounded_overrides: dict[tuple[str, bytes], int],
) -> None:
    global _WORKER_WORD_LIST
    _WORKER_WORD_LIST = word_list
    partition_functions._get_feedback_matrix(word_list)
    partition_functions.install_bounded_guess_overrides(bounded_overrides)


def run_algorithm_and_check(
    word_list: list[str],
    answer: str,
    algorithm: AlgorithmFunction,
    word_function: WordFunction,
    guesses: list[dict[str, str]] | None = None,
) -> tuple[int, bool]:
    guess_history = guesses if guesses is not None else []

    def record_guess(guess: str, feedback: f.Feedback) -> None:
        guess_history.append(
            {"guess": guess, "feedback": f.feedback_to_text(feedback)}
        )

    try:
        attempts = algorithm(
            word_list.copy(),
            answer,
            word_function,
            show_progress=False,
            on_guess=record_guess,
        )
    except (RuntimeError, AssertionError, ValueError):
        return -1, False

    return attempts, True


def _process_answer_batch(answers: list[str]) -> list[dict[str, object]]:
    games: list[dict[str, object]] = []
    for answer in answers:
        guesses: list[dict[str, str]] = []
        attempts, solved = run_algorithm_and_check(
            _WORKER_WORD_LIST,
            answer,
            partition.partition_algorithm,
            _unused_word_function,
            guesses,
        )
        games.append(
            {
                "answer": answer,
                "attempts": attempts,
                "solved": solved,
                "guesses": guesses,
            }
        )
    return games


def _unused_word_function(candidates: list[str]) -> str:
    return candidates[0]


def run_all_answers(
    word_list: list[str],
    output_path: Path,
    max_workers: int | None = None,
    batch_size: int = 25,
) -> tuple[int, int]:
    if batch_size <= 0:
        raise ValueError("batch_size deve ser maior que zero.")
    if max_workers is not None and max_workers <= 0:
        raise ValueError("max_workers deve ser maior que zero.")

    total_answers = len(word_list)
    games: list[dict[str, object]] = []
    payload: dict[str, object] = {
        "format_version": 1,
        "algorithm": "partition",
        "word_list_key": f.word_list_key(word_list),
        "settings": {"cost_power": 2, "max_attempts": 6},
        "complete": False,
        "completed_games": 0,
        "total_games": total_answers,
        "games": games,
    }
    f.write_json_checkpoint(output_path, payload)
    if not total_answers:
        payload["complete"] = True
        payload["summary"] = f.summarize_evaluation_games(games)
        f.write_json_checkpoint(output_path, payload)
        return 0, 0

    bounded_overrides, override_report = partition_functions.prepare_bounded_guess_overrides(
        word_list,
        max_attempts=6,
    )
    for branch_size, baseline_attempts, guess, bounded_attempts in override_report:
        print(
            f"Fallback limitado: ramo com {branch_size} candidatas, "
            f"p=2 chegava a {baseline_attempts}; {guess} limita a "
            f"{bounded_attempts} tentativas."
        )

    requested_workers = max_workers or os.cpu_count() or 1
    batch_count = (total_answers + batch_size - 1) // batch_size
    worker_count = min(requested_workers, max(1, batch_count))
    answer_batches = (
        word_list[start:start + batch_size]
        for start in range(0, total_answers, batch_size)
    )

    print(
        f"Processando {total_answers} respostas com o peso p=2 "
        f"em {worker_count} processos."
    )
    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=_initialize_worker,
        initargs=(word_list, bounded_overrides),
    ) as executor:
        for batch_games in executor.map(_process_answer_batch, answer_batches):
            games.extend(batch_games)
            payload["completed_games"] = len(games)
            f.write_json_checkpoint(output_path, payload)
            print(f"Respostas processadas: {len(games)}/{total_answers}")

    payload["complete"] = True
    payload["summary"] = f.summarize_evaluation_games(games)
    f.write_json_checkpoint(output_path, payload)
    return total_answers, total_answers


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Avaliar todas as respostas com o algoritmo de partição."
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="número máximo de processos (padrão: todos os processadores)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="respostas por lote (padrão: 25)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PARTITION_RESULTS_PATH,
        help="caminho do JSON de resultados",
    )
    args = parser.parse_args(argv)

    initial_word_list = f.file_to_list(str(WORD_LIST_PATH))
    answers_processed, simulations = run_all_answers(
        initial_word_list,
        args.output,
        max_workers=args.workers,
        batch_size=args.batch_size,
    )
    print(f"Simulações concluídas: {simulations} para {answers_processed} respostas.")
    print(f"Resultados salvos em: {args.output}")


if __name__ == "__main__":
    main()
