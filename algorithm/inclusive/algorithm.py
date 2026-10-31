"""Inclusive solver implementation."""

from collections.abc import Callable

from algorithm import functions as f
from algorithm import termo_implementation as t
from . import functions as strategy_functions

FilterFunction = Callable[[list[str], f.Feedback], list[str]]
ExactFilterFunction = Callable[[list[str], str, f.Feedback], list[str]]
WordFunction = Callable[[list[str]], str]


def algorithm_step(
    word_list: list[str],
    answer: str,
    word_function: WordFunction,
    filter_function: FilterFunction,
    show_progress: bool = True,
    accepted_words: set[str] | None = None,
    exact_filter: ExactFilterFunction | None = None,
) -> list[str]:
    """Run one guess and retain answers consistent with its feedback."""
    guess = word_function(word_list)
    if show_progress:
        print(f"Guess: {guess}")
    if guess.upper() == answer.upper():
        if show_progress:
            print("The algorithm find the anwser!\n")
        return []

    num_words_before = len(word_list)
    feedback = t.evaluate_guess(
        answer,
        guess,
        accepted_words if accepted_words is not None else set(word_list),
    )
    if exact_filter is not None:
        word_list = exact_filter(word_list, guess, feedback)
    else:
        word_list = filter_function(word_list, feedback)
    if not word_list:
        raise RuntimeError(
            "Nenhuma palavra candidata restou após o feedback. "
            "Verifique se a resposta está na lista de palavras e se o feedback está correto."
        )
    if show_progress:
        f.reading_word_list(word_list, 15)
        print(
            f"Possible words reduced from {num_words_before} to {len(word_list)}"
        )
    return word_list


def inclusive_algorithm(
    word_list: list[str],
    answer: str,
    word_function: WordFunction,
    show_progress: bool = True,
) -> int:
    """Solve with the inclusive strategy and exact observed feedback."""
    answer = answer.strip().upper()
    accepted_words = {word.strip().upper() for word in word_list}
    if answer not in accepted_words:
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
            strategy_functions.inclusive_filter_by_feedback,
            show_progress,
            accepted_words,
            strategy_functions.consistent_filter,
        )
        count += 1
    return count
