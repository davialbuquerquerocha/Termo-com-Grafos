from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from termo import InvalidWordError, evaluate_guess
from termo import score_guess


@dataclass(frozen=True)
class GuessFeedback:
    guess: str
    black: tuple[tuple[str, int], ...]
    yellow: tuple[tuple[str, int], ...]
    green: tuple[tuple[str, int], ...]


def reading_letters_count(letters_count: list[tuple[str, int, int]]):
    for tuple in letters_count:
            print(f"Letter: {tuple[0]}, Position: {tuple[1]}, Count: {tuple[2]}")

def reading_letters_pos(letters_pos: list[tuple[str, int]]):
    for tuple in letters_pos:
            print(f"Letter: {tuple[0]}, Position: {tuple[1]}")

def create_letters_count_file(file_name: str) -> list[tuple[str, int, int]]:
    letters_pos = []
    letters_count = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word_letters = list(line.strip())
            c = 1
            for letter in word_letters:
                if (letter, c) not in letters_pos:
                    letters_pos.append((letter, c))
                    letters_count.append((letter, c, 1))
                else:
                    letters_count[letters_pos.index((letter, c))] = (letter, c, letters_count[letters_pos.index((letter, c))][2] + 1)
                c += 1
        file.close()
    return letters_count 

def create_letters_count_list(words_list: list[str]) -> list[tuple[str, int, int]]:
    counts: dict[tuple[str, int], int] = {}
    for word in words_list:
        for position, letter in enumerate(word.strip(), start=1):
            key = (letter, position)
            counts[key] = counts.get(key, 0) + 1
    return [(letter, position, count) for (letter, position), count in counts.items()]

def best_letter_by_position(
    letters_count: list[tuple[str, int, int]],
    position: int,
    blacklist: list[str],
) -> tuple[str, int, int]:
    eligible_letters = [
        letter for letter in letters_count
        if letter[1] == position and letter[0] not in blacklist
    ]
    if not eligible_letters:
        raise ValueError(f"No eligible letters found for position {position}.")
    best_letter = max(eligible_letters, key=lambda letter: letter[2])
    return best_letter

def filter_file(file_name: str, letter_sequence: list[str]) -> list[str]:
    prefix = ''.join(letter_sequence)
    filtered_words = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word = line.strip()
            if word and word.startswith(prefix):
                filtered_words.append(word)
    return filtered_words

def filter_list(words_list: list[str], letter_sequence: list[str]) -> list[str]:
    prefix = ''.join(letter_sequence)
    filtered_words = [word for word in words_list if word.startswith(prefix)]
    return filtered_words

def file_to_list(file_name: str) -> list[str]:
    words_list = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word = line.strip()
            if word:
                words_list.append(word)
    return words_list

def find_best_word(words_list: list[str]) -> list[tuple[str, int, int]]:
    count_letters = create_letters_count_list
    select_best_letter = best_letter_by_position
    filter_words = filter_list
    selected_letters = []
    candidates = words_list
    for position in range(1, 6):
        letters_count = count_letters(candidates)
        blacklist = [letter[0] for letter in selected_letters]
        best_letter = select_best_letter(letters_count, position, blacklist)
        selected_letters.append(best_letter)
        if position < 5:
            prefix = [letter[0] for letter in selected_letters]
            candidates = filter_words(candidates, prefix)
    return selected_letters


def black_letter(word_list: list[str], letter: str) -> list[str]:
    return [word for word in word_list if letter not in word]


def alg_yellow_letter(word_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    letter, position = letter_pos
    index = position - 1
    return [
        word for word in word_list
        if index >= len(word) or word[index] != letter
    ]

def res_yellow_letter():
    pass

def alg_green_letter(word_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    letter, position = letter_pos
    index = position - 1
    return [
        word for word in word_list
        if index >= len(word) or word[index] != letter
    ]

def res_green_letter():
    pass

def letters_count_to_word(letters_count: list[tuple[str, int, int]]) -> str:
    sorted_letters = sorted(letters_count, key=lambda x: x[1])
    return ''.join(letter[0] for letter in sorted_letters)

def _select_informative_guess(
    words: list[str],
    used_guesses: set[str],
    black_letters: set[str],
    known_letters: set[str],
    tested_positions: set[tuple[str, int]],
    letter_counts: dict[tuple[str, int], int],
) -> str:
    available_words = [word for word in words if word not in used_guesses]
    if not available_words:
        raise RuntimeError("No unused guesses remain before the stopping condition.")

    def information_score(word: str) -> tuple[int, int, int, int, int]:
        new_positions = {
            (letter, position)
            for position, letter in enumerate(word, start=1)
            if letter not in black_letters
            and (letter, position) not in tested_positions
        }
        new_letters = {
            letter for letter, _ in new_positions
            if letter not in known_letters
        }
        black_letter_count = sum(letter in black_letters for letter in word)
        known_letter_positions = sum(
            letter in known_letters for letter, _ in new_positions
        )
        frequency_score = sum(
            letter_counts.get((letter, position), 0)
            for letter, position in new_positions
        )
        return (
            len(new_letters),
            len(new_positions),
            known_letter_positions,
            -black_letter_count,
            frequency_score,
        )

    return max(available_words, key=information_score)


def step1(
    answer: str,
    word_file: str = 'termo_palavras_aceitas.txt',
) -> list[GuessFeedback]:
    """Make guesses that maximize untested letter and position information."""
    answer = answer.strip().upper()
    if not answer.isalpha():
        raise InvalidWordError(f"invalid answer word: {answer!r}")
    if len(answer) != 5:
        raise InvalidWordError(
            f"invalid answer word {answer!r}: expected 5 letters, got {len(answer)}"
        )

    words = [
        word.upper()
        for word in file_to_list(word_file)
        if word.isalpha() and len(word) == len(answer)
    ]
    if not words:
        raise ValueError(
            f"No valid {len(answer)}-letter words found in {word_file!r}."
        )

    wordlist = set(words)
    letter_counts = {
        (letter, position): count
        for letter, position, count in create_letters_count_list(words)
    }
    used_guesses: set[str] = set()
    black_feedback: set[tuple[str, int]] = set()
    yellow_feedback: set[tuple[str, int]] = set()
    green_feedback: set[tuple[str, int]] = set()
    positive_positions: set[tuple[str, int]] = set()
    known_letter_counts: dict[str, int] = {}
    history: list[GuessFeedback] = []
    attempt = 0

    while True:
        known_feedback = yellow_feedback | green_feedback
        known_letters = {letter for letter, _ in known_feedback}
        black_letters = {
            letter for letter, _ in black_feedback
            if letter not in known_letters
        }

        candidates = words
        for letter in black_letters:
            candidates = black_letter(candidates, letter)
        for letter_pos in positive_positions:
            candidates = alg_yellow_letter(candidates, letter_pos)

        unused_candidates = [
            word for word in candidates if word not in used_guesses
        ]
        if not unused_candidates:
            unused_candidates = [
                word for word in words if word not in used_guesses
            ]
        if not unused_candidates:
            raise RuntimeError(
                "No unused guesses remain before five distinct positive pairs are known."
            )

        guess = _select_informative_guess(
            unused_candidates,
            used_guesses,
            black_letters,
            known_letters,
            positive_positions,
            letter_counts,
        )
        used_guesses.add(guess)
        attempt += 1

        black, yellow, green = evaluate_guess(answer, guess, wordlist)
        history.append(
            GuessFeedback(
                guess=guess,
                black=tuple(black),
                yellow=tuple(yellow),
                green=tuple(green),
            )
        )
        print(f"Tentativa {attempt}: {guess}")
        print(f"Preto: {black} | Amarelo: {yellow} | Verde: {green}")

        black_feedback.update(black)
        green_feedback.update(green)
        positive_positions.update(yellow)
        positive_positions.update(green)
        positive_counts_this_guess: dict[str, int] = {}
        for letter, _ in yellow + green:
            positive_counts_this_guess[letter] = (
                positive_counts_this_guess.get(letter, 0) + 1
            )
        for letter, count in positive_counts_this_guess.items():
            known_letter_counts[letter] = max(
                known_letter_counts.get(letter, 0),
                count,
            )
        yellow_feedback.update(yellow)
        green_letters = {letter for letter, _ in green_feedback}
        yellow_feedback = {
            letter_pos
            for letter_pos in yellow_feedback
            if letter_pos[0] not in green_letters
        }
        print(
            "Histórico acumulado: "
            f"pretas={sorted(black_feedback, key=lambda item: (item[1], item[0]))}, "
            f"amarelas={sorted(yellow_feedback, key=lambda item: (item[1], item[0]))}, "
            f"verdes={sorted(green_feedback, key=lambda item: (item[1], item[0]))}, "
            f"pares positivos distintos={sorted(positive_positions, key=lambda item: (item[1], item[0]))}, "
            f"ocorrências positivas conhecidas={known_letter_counts}"
        )

        if sum(known_letter_counts.values()) >= 5:
            print("Condição de parada atingida: cinco ocorrências positivas identificadas.")
            return history


def step2(
    history: list[GuessFeedback],
    solution_file: str = 'termo_palavras_aceitas.txt',
    possible_answers: list[str] | None = None,
) -> str:
    """Choose the most likely answer consistent with the accumulated feedback."""
    if not history:
        raise ValueError("Cannot infer an answer from an empty guess history.")

    if possible_answers is None:
        solutions = [
            word.upper()
            for word in file_to_list(solution_file)
            if word.isalpha() and len(word) == len(history[0].guess)
        ]
        if not solutions:
            raise ValueError(
                f"No valid {len(history[0].guess)}-letter solutions found in {solution_file!r}."
            )
        possible_answers = [
            answer for answer in solutions
            if all(_matches_feedback(answer, attempt) for attempt in history)
        ]
    if not possible_answers:
        raise ValueError("No solution matches the feedback history from step1.")

    letter_counts = {
        (letter, position): count
        for letter, position, count in create_letters_count_list(possible_answers)
    }
    best_answer = max(
        possible_answers,
        key=lambda word: sum(
            letter_counts.get((letter, position), 0)
            for position, letter in enumerate(word, start=1)
        ),
    )
    print(
        f"Step2: {len(possible_answers)} resposta(s) compatível(is); "
        f"melhor candidata por frequência posicional: {best_answer}"
    )
    return best_answer


def _matches_feedback(answer: str, attempt: GuessFeedback) -> bool:
    return score_guess(answer, attempt.guess) == (
        list(attempt.black),
        list(attempt.yellow),
        list(attempt.green),
    )


@lru_cache(maxsize=1)
def _build_feedback_matrix(words: tuple[str, ...]) -> np.ndarray:
    """Precompute each guess's encoded feedback against every answer."""
    letter_ids = {
        letter: index
        for index, letter in enumerate(sorted({letter for word in words for letter in word}))
    }
    encoded_words = np.asarray(
        [[letter_ids[letter] for letter in word] for word in words],
        dtype=np.uint8,
    )
    word_count = len(words)
    pattern_matrix = np.empty((word_count, word_count), dtype=np.uint8)
    powers_of_three = np.asarray([1, 3, 9, 27, 81], dtype=np.uint16)
    batch_size = 128

    for batch_start in range(0, word_count, batch_size):
        guesses = encoded_words[batch_start:batch_start + batch_size]
        greens = guesses[:, None, :] == encoded_words[None, :, :]
        marks = np.zeros(greens.shape, dtype=np.uint8)
        marks[greens] = 2

        for position in range(guesses.shape[1]):
            answer_counts = (
                guesses[:, None, position, None] == encoded_words[None, :, :]
            ).sum(axis=2)
            green_counts = (
                (guesses[:, None, :] == guesses[:, None, position, None]) & greens
            ).sum(axis=2)
            previous_yellow_counts = np.zeros(answer_counts.shape, dtype=np.uint8)
            for previous_position in range(position):
                same_letter = (
                    guesses[:, position] == guesses[:, previous_position]
                )[:, None]
                previous_yellow_counts += (
                    same_letter & (marks[:, :, previous_position] == 1)
                )

            yellow = (
                ~greens[:, :, position]
                & (answer_counts > green_counts + previous_yellow_counts)
            )
            marks[:, :, position] = np.where(greens[:, :, position], 2, yellow)

        encoded_patterns = (
            marks.astype(np.uint16) * powers_of_three[None, None, :]
        ).sum(axis=2).astype(np.uint8)
        pattern_matrix[batch_start:batch_start + len(guesses)] = encoded_patterns

    return pattern_matrix


class MinimaxSolver:
    """Choose accepted-word guesses by minimizing the worst remaining bucket."""

    def __init__(self, words: list[str]) -> None:
        self.words = tuple(words)
        self.word_to_index = {word: index for index, word in enumerate(words)}
        self.patterns = _build_feedback_matrix(self.words)

    @lru_cache(maxsize=20_000)
    def choose_guess(
        self,
        possible_answers: tuple[int, ...],
        use_all_guesses: bool,
    ) -> int:
        if not possible_answers:
            raise ValueError("Cannot choose a guess without possible answers.")
        if len(possible_answers) == 1:
            return possible_answers[0]

        answer_indices = np.asarray(possible_answers, dtype=np.intp)
        possible_set = set(possible_answers)
        guess_pool = (
            range(len(self.words))
            if use_all_guesses
            else possible_answers
        )
        best_key: tuple[int, int, int, int] | None = None
        best_guess = -1
        batch_size = 256

        for batch_start in range(0, len(guess_pool), batch_size):
            batch_guess_ids = list(
                guess_pool[batch_start:batch_start + batch_size]
                if isinstance(guess_pool, tuple)
                else range(batch_start, min(batch_start + batch_size, len(self.words)))
            )
            guess_indices = np.asarray(batch_guess_ids, dtype=np.uint32)
            pattern_codes = self.patterns[guess_indices[:, None], answer_indices]
            bucket_offsets = (
                np.arange(len(guess_indices), dtype=np.uint32)[:, None] * 243
            )
            flattened_buckets = (
                pattern_codes.astype(np.uint32) + bucket_offsets
            ).ravel()
            bucket_counts = np.bincount(
                flattened_buckets,
                minlength=len(guess_indices) * 243,
            ).reshape(len(guess_indices), 243)
            worst_bucket = bucket_counts.max(axis=1)
            expected_remaining_numerator = (
                bucket_counts.astype(np.uint32) ** 2
            ).sum(axis=1)

            for offset, guess_index_value in enumerate(guess_indices):
                guess_index = int(guess_index_value)
                key = (
                    int(worst_bucket[offset]),
                    int(expected_remaining_numerator[offset]),
                    0 if guess_index in possible_set else 1,
                    guess_index,
                )
                if best_key is None or key < best_key:
                    best_key = key
                    best_guess = guess_index

        return best_guess

    def solve(self, answer: str) -> list[int]:
        answer_index = self.word_to_index[answer]
        possible_answers = tuple(range(len(self.words)))
        guesses: list[int] = []

        while True:
            guess_index = self.choose_guess(possible_answers, True)
            guesses.append(guess_index)
            if guess_index == answer_index:
                return guesses

            observed_pattern = int(self.patterns[guess_index, answer_index])
            candidate_array = np.asarray(possible_answers, dtype=np.intp)
            matching_offsets = np.flatnonzero(
                self.patterns[guess_index, candidate_array] == observed_pattern
            )
            updated_answers = tuple(
                int(candidate_array[offset]) for offset in matching_offsets
            )
            if len(updated_answers) >= len(possible_answers):
                raise RuntimeError(
                    "Minimax guess did not reduce the possible-answer set."
                )
            possible_answers = updated_answers


def play_game(
    answer: str,
    word_file: str = 'termo_palavras_aceitas.txt',
) -> int:
    """Play using adaptive minimax guesses until the exact answer is found."""
    answer = answer.strip().upper()
    if not answer.isalpha() or len(answer) != 5:
        raise InvalidWordError(
            f"invalid answer word {answer!r}: expected 5 alphabetic letters"
        )

    accepted_words = {
        word.upper()
        for word in file_to_list(word_file)
        if word.isalpha() and len(word) == len(answer)
    }
    if answer not in accepted_words:
        raise InvalidWordError(
            f"invalid answer word {answer!r}: word is not in the accepted word list"
        )

    words = sorted(accepted_words)
    solver = MinimaxSolver(words)
    guess_indices = solver.solve(answer)
    for attempt_number, guess_index in enumerate(guess_indices, start=1):
        guess = words[guess_index]
        black, yellow, green = evaluate_guess(answer, guess, accepted_words)
        print(f"Tentativa {attempt_number}: {guess}")
        print(f"Preto: {black} | Amarelo: {yellow} | Verde: {green}")
        if len(green) == len(answer):
            print(f"Resposta encontrada na tentativa {attempt_number}: {answer}")
            return attempt_number
    raise RuntimeError("Minimax solver ended without guessing the answer.")


def benchmark_all_answers(
    word_file: str = 'termo_palavras_aceitas.txt',
) -> dict[str, object]:
    """Measure minimax solve lengths for every valid accepted word."""
    words = sorted({
        word.upper()
        for word in file_to_list(word_file)
        if word.isalpha() and len(word) == 5
    })
    if not words:
        raise ValueError(f"No valid five-letter words found in {word_file!r}.")

    solver = MinimaxSolver(words)
    distribution: dict[int, int] = {}
    failures: list[tuple[str, str]] = []
    total_guesses = 0
    max_attempts = 0
    worst_words: list[str] = []

    for answer in words:
        try:
            attempts = len(solver.solve(answer))
        except (RuntimeError, ValueError) as error:
            failures.append((answer, str(error)))
            continue
        distribution[attempts] = distribution.get(attempts, 0) + 1
        total_guesses += attempts
        if attempts > max_attempts:
            max_attempts = attempts
            worst_words = [answer]
        elif attempts == max_attempts:
            worst_words.append(answer)

    solved = sum(distribution.values())
    return {
        "total_answers": len(words),
        "solved": solved,
        "failures": failures,
        "distribution": dict(sorted(distribution.items())),
        "total_guesses": total_guesses,
        "average_guesses": total_guesses / solved if solved else 0.0,
        "max_attempts": max_attempts,
        "worst_words": worst_words,
        "within_six": solved == len(words) and max_attempts <= 6,
    }


if __name__ == "__main__":
    answer = input("Digite a palavra resposta: ").strip().upper()
    play_game(answer)
