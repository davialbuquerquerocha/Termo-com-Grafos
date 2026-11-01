"""Partition-based solver implementation."""

from collections.abc import Callable

import numpy as np

from algorithm import functions as f
from algorithm import termo_implementation as t
from . import functions as helpers

WordFunction = Callable[[list[str]], str]


def partition_algorithm(
    word_list: list[str],
    answer: str,
    word_function: WordFunction,
    show_progress: bool = True,
) -> int:
    """
    Solve using exact feedback partitions with squared group sizes.

    ``word_function`` is retained for API compatibility and intentionally ignored.
    """
    answer = answer.strip().upper()
    normalized_words = [word.strip().upper() for word in word_list]
    accepted_words = set(normalized_words)
    if answer not in accepted_words:
        raise ValueError(
            f"A resposta {answer!r} não está na lista de palavras candidatas. "
            "O algoritmo exclusivo só consegue encontrá-la se ela estiver nessa lista."
        )

    matrix, word_indices, word_key = helpers._get_feedback_matrix(normalized_words)
    possible_answers = normalized_words.copy()
    possible_indices = list(range(len(normalized_words)))
    guessed_indices: set[int] = set()
    count = 0

    while True:
        if len(possible_answers) <= 2:
            guess = possible_answers[0]
            guess_index = word_indices[guess]
        elif count == 1 and (
            override_index := helpers._BOUNDED_GUESS_OVERRIDES.get(
                (word_key, helpers._candidate_state_key(possible_indices))
            )
        ) is not None:
            guess_index = override_index
            guess = normalized_words[guess_index]
        elif count == 0:
            guess_index = helpers._FIRST_GUESS_CACHE.get(word_key, -1)
            if guess_index < 0:
                guess_index = helpers._choose_partition_guess(
                    possible_indices,
                    guessed_indices,
                    matrix,
                    word_key,
                )
                helpers._FIRST_GUESS_CACHE[word_key] = guess_index
            guess = normalized_words[guess_index]
        else:
            guess_index = helpers._choose_partition_guess(
                possible_indices,
                guessed_indices,
                matrix,
                word_key,
            )
            guess = normalized_words[guess_index]

        if guess_index in guessed_indices:
            raise RuntimeError(f"O palpite {guess!r} seria repetido.")
        guessed_indices.add(guess_index)
        count += 1
        if show_progress:
            print(f"Guess: {guess}")
        if guess == answer:
            if show_progress:
                print("The algorithm find the anwser!\n")
            return count

        feedback = t.evaluate_guess(answer, guess, accepted_words)
        feedback_code = helpers._feedback_code(feedback)
        candidate_indices = np.asarray(possible_indices, dtype=np.intp)
        possible_indices = candidate_indices[
            matrix[guess_index, candidate_indices] == feedback_code
        ].tolist()
        possible_answers = [normalized_words[index] for index in possible_indices]
        assert possible_answers, "O feedback eliminou todas as respostas possíveis."
        assert answer in possible_answers, "A resposta correta foi removida dos candidatos."
        if show_progress:
            f.reading_word_list(possible_answers, 15)
            print(
                f"Possible words reduced to {len(possible_answers)}"
            )
