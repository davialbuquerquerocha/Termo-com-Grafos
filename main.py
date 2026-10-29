import csv
from collections.abc import Callable
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

ALGORITHMS: tuple[tuple[str, AlgorithmFunction], ...] = (
    ("inclusive", algo2.inclusive_algorithm),
    ("exclusive", algo2.exclusive_algorithm),
)


def run_algorithm_and_check(
    word_list: list[str],
    answer: str,
    algorithm: AlgorithmFunction,
    word_function: WordFunction,
) -> tuple[int, bool]:
    last_guess = ""

    def remember_guess(candidates: list[str]) -> str:
        nonlocal last_guess
        last_guess = word_function(candidates).strip().upper()
        return last_guess

    try:
        attempts = algorithm(
            word_list.copy(),
            answer,
            remember_guess,
            show_progress=False,
        )
    except RuntimeError:
        return -1, False

    solved = last_guess == answer.strip().upper()
    return (attempts if solved else -1), solved


def run_all_answers(
    word_list: list[str],
    output_path: Path,
) -> tuple[int, int]:
    total_answers = len(word_list)
    completed_answers = 0
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ("answer", "algorithm", "word_function", "attempts", "solved")
        )

        for answer in word_list:
            for algorithm_name, algorithm in ALGORITHMS:
                for word_function_name, word_function in WORD_FUNCTIONS:
                    attempts, solved = run_algorithm_and_check(
                        word_list,
                        answer,
                        algorithm,
                        word_function,
                    )
                    writer.writerow(
                        (
                            answer,
                            algorithm_name,
                            word_function_name,
                            attempts,
                            solved,
                        )
                    )

            completed_answers += 1
            if completed_answers % 100 == 0:
                file.flush()
                print(f"Respostas processadas: {completed_answers}/{total_answers}")

    return completed_answers, completed_answers * len(ALGORITHMS) * len(WORD_FUNCTIONS)


if __name__ == "__main__":
    initial_word_list = f.file_to_list(str(WORD_LIST_PATH))
    answers_processed, simulations = run_all_answers(
        initial_word_list,
        RESULTS_PATH,
    )
    print(f"Simulações concluídas: {simulations} para {answers_processed} respostas.")
    print(f"Resultados salvos em: {RESULTS_PATH}")
