from collections.abc import Callable
from pathlib import Path

if __package__:
    from . import functions as f
    from . import termo_implementation as t
else:
    import functions as f
    import termo_implementation as t

DATASET_PATH = Path(__file__).resolve().parent.parent / "dataset" / "termo_palavras_aceitas.txt"
initial_word_list = f.file_to_list(str(DATASET_PATH))

FilterFunction = Callable[[list[str], f.Feedback], list[str]]
WordFunction = Callable[[list[str]], str]

def algorithm_step(word_list: list[str], answer: str, word_function: WordFunction, filter_function: FilterFunction, show_progress: bool = True) -> list[str]:
    """
    Runs one guess and filters the remaining possible answers.
    """
    guess = word_function(word_list)
    if show_progress:
        print(f"Guess: {guess}")
    if guess.upper() == answer.upper():
        if show_progress:
            print("The algorithm find the anwser!\n")
        return []
    num_words_before = f.count_words(word_list)
    feedback = t.evaluate_guess(answer, guess, set(word_list))
    word_list = filter_function(word_list, feedback)
    if not word_list:
        raise RuntimeError(
            "Nenhuma palavra candidata restou após o feedback. "
            "Verifique se a resposta está na lista de palavras e se o feedback está correto."
        )
    if show_progress:
        f.reading_word_list(word_list, 15)
        num_words_after = f.count_words(word_list)
        print(f"Possible words reduced from {num_words_before} to {num_words_after}")
    return word_list


def inclusive_algorithm(word_list: list[str], answer: str, word_function: WordFunction, show_progress: bool = True) -> int:
    """
    Runs algorithm_step with the inclusive filter until it finds the answer.
    """
    answer = answer.strip().upper()
    if not f.is_word_in_list(answer, word_list):
        raise ValueError(
            f"A resposta {answer!r} não está na lista de palavras candidatas. "
            "O algoritmo inclusivo só consegue encontrá-la se ela estiver nessa lista."
        )

    count = 0
    while word_list:
        word_list = algorithm_step(
            word_list,
            answer,
            word_function,
            f.inclusive_filter_by_feedback,
            show_progress,
        )
        count += 1
    return count

def exclusive_algorithm(word_list: list[str], answer: str, word_function: WordFunction, show_progress: bool = True) -> int:
    answer = answer.strip().upper()
    if not f.is_word_in_list(answer, word_list):
        raise ValueError(
            f"A resposta {answer!r} não está na lista de palavras candidatas. "
            "O algoritmo exclusivo só consegue encontrá-la se ela estiver nessa lista."
        )

    possible_answers = [word.strip().upper() for word in word_list]
    possible_guesses = possible_answers.copy()
    guessed_words: set[str] = set()
    count = 0

    while len(possible_answers) > 1:
        available_guesses = [
            word for word in possible_guesses if word not in guessed_words
        ]
        if not available_guesses:
            available_guesses = [
                word for word in possible_answers if word not in guessed_words
            ]
        if not available_guesses:
            raise RuntimeError(
                "Não há guesses não utilizados para distinguir as respostas restantes."
            )

        guess_made = ""

        def remember_guess(candidates: list[str]) -> str:
            nonlocal guess_made
            guess_made = word_function(candidates)
            guessed_words.add(guess_made.strip().upper())
            return guess_made

        def filter_candidates(
            candidates: list[str],
            feedback: f.Feedback,
        ) -> list[str]:
            nonlocal possible_answers
            possible_answers = f.inclusive_filter_by_feedback(
                possible_answers,
                feedback,
            )
            if not possible_answers:
                raise RuntimeError(
                    "Nenhuma resposta possível restou após o feedback. "
                    "Verifique se a resposta está na lista de palavras e se o feedback está correto."
                )

            filtered_guesses = [
                word
                for word in f.exclusive_filter_by_feedback(candidates, feedback)
                if word.strip().upper() not in guessed_words
            ]
            if not filtered_guesses:
                varying_positions = {
                    position
                    for position in range(len(possible_answers[0]))
                    if len({word[position] for word in possible_answers}) > 1
                }
                unknown_letters = {
                    word[position]
                    for word in possible_answers
                    for position in varying_positions
                }
                probe_words = [
                    word.strip().upper()
                    for word in word_list
                    if word.strip().upper() not in guessed_words
                    and len(word.strip()) == len(possible_answers[0])
                ]
                if unknown_letters and probe_words:
                    best_coverage = max(
                        len(set(word) & unknown_letters) for word in probe_words
                    )
                    filtered_guesses = [
                        word
                        for word in probe_words
                        if len(set(word) & unknown_letters) == best_coverage
                    ]
            if not filtered_guesses:
                filtered_guesses = [
                    word for word in possible_answers if word not in guessed_words
                ]
            if not filtered_guesses:
                filtered_guesses = [
                    word
                    for word in word_list
                    if word.strip().upper() not in guessed_words
                ]
            return filtered_guesses

        possible_guesses = algorithm_step(
            available_guesses,
            answer,
            remember_guess,
            filter_candidates,
            show_progress,
        )
        count += 1

        if guess_made.upper() == answer:
            return count

    final_answer = possible_answers[0]
    if final_answer != answer:
        raise RuntimeError(
            f"A única resposta possível ({final_answer!r}) não corresponde à resposta informada."
        )

    algorithm_step(
        possible_answers,
        answer,
        word_function,
        f.inclusive_filter_by_feedback,
        show_progress,
    )
    return count + 1

def run_all(
    word_list: list[str],
    answer: str,
    show_progress: bool = True,
    exclusive: bool = True,
) -> dict[str, int]:
    algorithm = exclusive_algorithm if exclusive else inclusive_algorithm
    algorithm_name = "exclusivo" if exclusive else "inclusivo"
    strategies = (
        ("position_true", "posição True", lambda candidates: f.find_best_word_by_letter_position(candidates, allow_repeated_letters=True)),
        ("position_false", "posição False", lambda candidates: f.find_best_word_by_letter_position(candidates, allow_repeated_letters=False)),
        ("frequency_true", "frequência True", lambda candidates: f.find_best_word_by_letter_frequency(candidates, allow_repeated_letters=True)),
        ("frequency_false", "frequência False", lambda candidates: f.find_best_word_by_letter_frequency(candidates, allow_repeated_letters=False)),
    )

    results: dict[str, int] = {}
    for result_key, strategy_name, word_function in strategies:
        attempts = algorithm(
            word_list.copy(),
            answer,
            word_function,
            show_progress,
        )
        results[result_key] = attempts
        print(
            f"O algoritmo {algorithm_name} de {strategy_name} "
            f"achou a resposta em {attempts} tentativas."
        )

    for result_key, strategy_name, _word_function in strategies:
        print(
            f"O algoritmo {algorithm_name} de {strategy_name} "
            f"achou a resposta em {results[result_key]} tentativas."
        )

    return results


if __name__ == "__main__":
    answer = input("Qual será a resposta do jogo?\n-> ")
    run_all(initial_word_list, answer)
