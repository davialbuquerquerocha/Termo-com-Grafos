import csv
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path

from algorithm.partition import algorithm as partition
from algorithm.partition import functions as partition_functions
from algorithm import functions as f

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
WORD_LIST_PATH = DATASET_DIR / "termo_palavras_aceitas.txt"
PARTITION_RESULTS_PATH = DATASET_DIR / "resultados_partition_busca_limitada.csv"

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
) -> tuple[int, bool]:
    try:
        attempts = algorithm(
            word_list.copy(),
            answer,
            word_function,
            show_progress=False,
        )
    except (RuntimeError, AssertionError, ValueError):
        return -1, False

    return attempts, True


def _process_answer_batch(
    answers: list[str],
) -> list[tuple[str, str, str, int, bool]]:
    rows: list[tuple[str, str, str, int, bool]] = []
    for answer in answers:
        attempts, solved = run_algorithm_and_check(
            _WORKER_WORD_LIST,
            answer,
            partition.partition_algorithm,
            _unused_word_function,
        )
        rows.append(
            (
                answer,
                "partition",
                "partition_p2_bounded",
                attempts,
                solved,
            )
        )
    return rows


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
    if not total_answers:
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                ("answer", "algorithm", "word_function", "attempts", "solved")
            )
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

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ("answer", "algorithm", "word_function", "attempts", "solved")
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
            completed_answers = 0
            for batch_rows in executor.map(
                _process_answer_batch,
                answer_batches,
            ):
                writer.writerows(batch_rows)
                previous_completed = completed_answers
                completed_answers += len(batch_rows)
                if completed_answers // 100 > previous_completed // 100:
                    file.flush()
                    print(
                        f"Respostas processadas: "
                        f"{completed_answers}/{total_answers}"
                    )

    return total_answers, total_answers


if __name__ == "__main__":
    initial_word_list = f.file_to_list(str(WORD_LIST_PATH))
    answers_processed, simulations = run_all_answers(
        initial_word_list,
        PARTITION_RESULTS_PATH,
    )
    print(f"Simulações concluídas: {simulations} para {answers_processed} respostas.")
    print(f"Resultados salvos em: {PARTITION_RESULTS_PATH}")
