import csv
from collections.abc import Callable
from pathlib import Path

import algorithm.functions as f
import algorithm.termo_implementation as t

DATASET_DIR = Path(__file__).resolve().parent / "dataset"
INITIAL_WORDS_LIST = f.file_to_list(str(DATASET_DIR / "termo_palavras_aceitas.txt"))


def algorithm_step(
    words_list: list[str],
    answer: str,
    word_function: Callable[[list[str]], str],
    mostrar_progresso: bool = True,
) -> list[str]:
    num_words_before = f.count_words(words_list)
    guess = word_function(words_list)
    if mostrar_progresso:
        print(f"Guess: {guess}")
    if guess.upper() == answer.upper():
        if mostrar_progresso:
            print("The algorithm find the anwser!\n")
        return []

    feedback = t.evaluate_guess(answer, guess, set(words_list))
    words_list = [
        candidate
        for candidate in words_list
        if t.score_guess(candidate, guess) == feedback
    ]
    if mostrar_progresso:
        f.reading_words_list(words_list, 15)
        num_words_after = f.count_words(words_list)
        print(f"Possible words reduced from {num_words_before} to {num_words_after}")
    return words_list


def algorithm(
    words_list: list[str],
    answer: str,
    word_function: Callable[[list[str]], str],
    mostrar_progresso: bool = True,
) -> int:
    count = 0
    while words_list:
        words_list = algorithm_step(
            words_list,
            answer,
            word_function,
            mostrar_progresso,
        )
        count += 1
    return count


def run_algorithm_and_check(
    words_list: list[str],
    answer: str,
    word_function: Callable[[list[str]], str],
) -> tuple[int, bool]:
    last_guess = ""

    def remember_guess(candidates: list[str]) -> str:
        nonlocal last_guess
        last_guess = word_function(candidates)
        return last_guess

    steps = algorithm(words_list.copy(), answer, remember_guess, mostrar_progresso=False)
    return steps, last_guess.upper() == answer.upper()


def run_all_answers(
    words_list: list[str],
    answers: list[str],
    output_path: Path,
) -> int:
    results = []
    strategies = (
        ("position", f.find_best_word_by_letter_position),
        ("frequency", f.find_best_word_by_letter_frequency),
    )

    for answer in answers:
        result_row: list[str | int | bool] = [answer]
        for _name, strategy in strategies:
            steps, solved = run_algorithm_and_check(words_list, answer, strategy)
            result_row.extend((steps, solved))
        results.append(result_row)

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            (
                "answer",
                "position_steps",
                "position_solved",
                "frequency_steps",
                "frequency_solved",
            )
        )
        writer.writerows(results)

    return len(results)


if __name__ == "__main__":
    results_path = DATASET_DIR / "resultados_algoritmos.csv"
    total = run_all_answers(
        INITIAL_WORDS_LIST,
        INITIAL_WORDS_LIST,
        results_path,
    )
    print(f"Simulações concluídas: {total} respostas.")
    print(f"Resultados salvos em: {results_path}")
