import csv
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path

from algorithm import algo2
from algorithm import functions as f

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
WORD_LIST_PATH = DATASET_DIR / "termo_palavras_aceitas.txt"
RESULTS_PATH = DATASET_DIR / "resultados_todas_palavras.csv"

WordFunction = Callable[[list[str]], str]
AlgorithmFunction = Callable[[list[str], str, WordFunction, bool], int]

WORD_FUNCTIONS: tuple[tuple[str, WordFunction], ...] = (
    (
        "position_true",
        lambda candidates: f.find_best_word_by_letter_position(
            candidates,
            allow_repeated_letters=True,
        ),
    ),
    (
        "position_false",
        lambda candidates: f.find_best_word_by_letter_position(
            candidates,
            allow_repeated_letters=False,
        ),
    ),
    (
        "frequency_true",
        lambda candidates: f.find_best_word_by_letter_frequency(
            candidates,
            allow_repeated_letters=True,
        ),
    ),
    (
        "frequency_false",
        lambda candidates: f.find_best_word_by_letter_frequency(
            candidates,
            allow_repeated_letters=False,
        ),
    ),
)

_WORKER_WORD_LIST: list[str] = []


def _initialize_worker(word_list: list[str]) -> None:
    global _WORKER_WORD_LIST
    _WORKER_WORD_LIST = word_list
    algo2._get_feedback_matrix(word_list)


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
        for word_function_name, word_function in WORD_FUNCTIONS:
            attempts, solved = run_algorithm_and_check(
                _WORKER_WORD_LIST,
                answer,
                algo2.inclusive_algorithm,
                word_function,
            )
            rows.append(
                (
                    answer,
                    "inclusive",
                    word_function_name,
                    attempts,
                    solved,
                )
            )

        attempts, solved = run_algorithm_and_check(
            _WORKER_WORD_LIST,
            answer,
            algo2.exclusive_algorithm,
            WORD_FUNCTIONS[0][1],
        )
        rows.append((answer, "exclusive", "partition", attempts, solved))
    return rows


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
            f"Processando {total_answers} respostas com "
            f"{worker_count} processos."
        )
        with ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=_initialize_worker,
            initargs=(word_list,),
        ) as executor:
            completed_answers = 0
            for batch_rows in executor.map(
                _process_answer_batch,
                answer_batches,
            ):
                writer.writerows(batch_rows)
                previous_completed = completed_answers
                completed_answers += len(batch_rows) // (
                    len(WORD_FUNCTIONS) + 1
                )
                if completed_answers // 100 > previous_completed // 100:
                    file.flush()
                    print(
                        f"Respostas processadas: "
                        f"{completed_answers}/{total_answers}"
                    )

    return total_answers, total_answers * (len(WORD_FUNCTIONS) + 1)


if __name__ == "__main__":
    initial_word_list = f.file_to_list(str(WORD_LIST_PATH))
    answers_processed, simulations = run_all_answers(
        initial_word_list,
        RESULTS_PATH,
    )
    print(f"Simulações concluídas: {simulations} para {answers_processed} respostas.")
    print(f"Resultados salvos em: {RESULTS_PATH}")
