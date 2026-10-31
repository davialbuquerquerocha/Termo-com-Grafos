from collections.abc import Callable
import hashlib
import os
from pathlib import Path
import random

import numpy as np

if __package__:
    from . import functions as f
    from . import termo_implementation as t
else:
    import functions as f
    import termo_implementation as t

DATASET_PATH = Path(__file__).resolve().parent.parent / "dataset" / "termo_palavras_aceitas.txt"
initial_word_list = f.file_to_list(str(DATASET_PATH))

FilterFunction = Callable[[list[str], f.Feedback], list[str]]
ExactFilterFunction = Callable[[list[str], str, f.Feedback], list[str]]
WordFunction = Callable[[list[str]], str]
FeedbackMatrix = np.ndarray

_FEEDBACK_MATRIX_CACHE: dict[str, FeedbackMatrix] = {}
_WORD_INDEX_CACHE: dict[str, dict[str, int]] = {}
_PARTITION_GUESS_CACHE: dict[tuple[str, bytes, tuple[int, ...]], int] = {}
_FIRST_GUESS_CACHE: dict[str, int] = {}
_MATRIX_VALIDATED: set[str] = set()
_FEEDBACK_PATTERN_COUNT = 3**5
_MATRIX_CHUNK_SIZE = 256


def _words_key(word_list: list[str]) -> str:
    digest = hashlib.sha256()
    for word in word_list:
        digest.update(word.strip().upper().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


_INITIAL_WORDS_KEY = _words_key(initial_word_list)


def _feedback_code(feedback: f.Feedback) -> int:
    marks = [0] * 5
    for letter, position in feedback[1]:
        marks[position - 1] = 1
    for letter, position in feedback[2]:
        marks[position - 1] = 2
    return sum(mark * (3**position) for position, mark in enumerate(marks))


def _build_feedback_matrix(word_list: list[str], path: Path) -> None:
    word_count = len(word_list)
    if not word_count:
        raise ValueError("A lista de palavras não pode estar vazia.")
    if any(len(word) != 5 for word in word_list):
        raise ValueError("A matriz de feedback exige palavras de cinco letras.")

    encoded_words = np.frombuffer(
        "".join(word_list).encode("ascii"),
        dtype=np.uint8,
    ).reshape(word_count, 5) - ord("A")
    answer_letter_counts = np.stack(
        [np.count_nonzero(encoded_words == letter, axis=1) for letter in range(26)],
        axis=1,
    )
    matrix = np.lib.format.open_memmap(
        path,
        mode="w+",
        dtype=np.uint8,
        shape=(word_count, word_count),
    )
    powers = np.array([1, 3, 9, 27, 81], dtype=np.uint8)

    for guess_index, guess in enumerate(encoded_words):
        green = encoded_words == guess
        marks = green.astype(np.uint8) * 2
        green_counts = {
            int(letter): green[:, guess == letter].sum(axis=1)
            for letter in np.unique(guess)
        }
        consumed_yellows: dict[int, np.ndarray] = {}
        for position, letter_value in enumerate(guess):
            letter = int(letter_value)
            if letter not in consumed_yellows:
                consumed_yellows[letter] = np.zeros(word_count, dtype=np.uint8)
            available = (
                answer_letter_counts[:, letter]
                - green_counts[letter]
                - consumed_yellows[letter]
            )
            yellow = ~green[:, position] & (available > 0)
            marks[yellow, position] = 1
            consumed_yellows[letter] += yellow
        matrix[guess_index] = np.sum(
            marks * powers,
            axis=1,
            dtype=np.uint16,
        ).astype(np.uint8)

    matrix.flush()
    del matrix


def _get_feedback_matrix(word_list: list[str]) -> tuple[FeedbackMatrix, dict[str, int], str]:
    normalized_words = [word.strip().upper() for word in word_list]
    key = _words_key(normalized_words)
    if key in _FEEDBACK_MATRIX_CACHE:
        return _FEEDBACK_MATRIX_CACHE[key], _WORD_INDEX_CACHE[key], key

    cache_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Termo"
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_path = cache_root / f"feedback_matrix_{key}.npy"
    matrix: FeedbackMatrix | None = None
    if cache_path.exists():
        try:
            cached_matrix = np.load(cache_path, mmap_mode="r")
        except (OSError, ValueError):
            cached_matrix = None
        if cached_matrix is not None:
            if (
                cached_matrix.shape == (len(normalized_words), len(normalized_words))
                and cached_matrix.dtype == np.uint8
            ):
                matrix = cached_matrix
            else:
                del cached_matrix

    if matrix is None:
        temporary_path = cache_path.with_name(f"{cache_path.stem}.tmp.npy")
        _build_feedback_matrix(normalized_words, temporary_path)
        temporary_path.replace(cache_path)
        matrix = np.load(cache_path, mmap_mode="r")

    index = {word: position for position, word in enumerate(normalized_words)}
    if key not in _MATRIX_VALIDATED:
        rng = random.Random(0)
        for _ in range(3000):
            guess_index = rng.randrange(len(normalized_words))
            answer_index = rng.randrange(len(normalized_words))
            expected = _feedback_code(
                t.score_guess(normalized_words[answer_index], normalized_words[guess_index])
            )
            if int(matrix[guess_index, answer_index]) != expected:
                raise RuntimeError(
                    "A matriz pré-calculada diverge de score_guess para "
                    f"{normalized_words[guess_index]!r}/{normalized_words[answer_index]!r}."
                )
        _MATRIX_VALIDATED.add(key)

    _FEEDBACK_MATRIX_CACHE[key] = matrix
    _WORD_INDEX_CACHE[key] = index
    return matrix, index, key


def _choose_partition_guess(
    possible_indices: list[int],
    guessed_indices: set[int],
    matrix: FeedbackMatrix,
    word_key: str,
) -> int:
    state_digest = hashlib.sha256(
        np.asarray(possible_indices, dtype=np.uint32).tobytes()
    ).digest()
    cache_key = word_key, state_digest, tuple(sorted(guessed_indices))
    cached_index = _PARTITION_GUESS_CACHE.get(cache_key)
    if cached_index is not None:
        return cached_index

    answer_indices = np.asarray(possible_indices, dtype=np.intp)
    possible_set = set(possible_indices)
    best_cost: int | None = None
    best_indices: list[int] = []
    candidate_count = matrix.shape[0]

    for start in range(0, candidate_count, _MATRIX_CHUNK_SIZE):
        stop = min(start + _MATRIX_CHUNK_SIZE, candidate_count)
        guess_indices = [
            index for index in range(start, stop)
            if index not in guessed_indices
        ]
        if not guess_indices:
            continue

        feedbacks = matrix[np.asarray(guess_indices), :][:, answer_indices]
        offsets = (
            np.arange(len(guess_indices), dtype=np.int32)[:, None]
            * _FEEDBACK_PATTERN_COUNT
        )
        grouped = np.bincount(
            (feedbacks.astype(np.int32) + offsets).ravel(),
            minlength=len(guess_indices) * _FEEDBACK_PATTERN_COUNT,
        ).reshape(len(guess_indices), _FEEDBACK_PATTERN_COUNT)
        costs = np.sum(grouped * grouped, axis=1, dtype=np.int64)
        chunk_best = int(costs.min())
        if best_cost is None or chunk_best < best_cost:
            best_cost = chunk_best
            best_indices = [
                guess_indices[index]
                for index in np.flatnonzero(costs == chunk_best)
            ]
        elif chunk_best == best_cost:
            best_indices.extend(
                guess_indices[index]
                for index in np.flatnonzero(costs == chunk_best)
            )

    if not best_indices:
        raise RuntimeError("Não há palpites aceitos ainda não utilizados.")
    selected_index = next(
        (index for index in best_indices if index in possible_set),
        best_indices[0],
    )
    _PARTITION_GUESS_CACHE[cache_key] = selected_index
    return selected_index


def algorithm_step(
    word_list: list[str],
    answer: str,
    word_function: WordFunction,
    filter_function: FilterFunction,
    show_progress: bool = True,
    accepted_words: set[str] | None = None,
    exact_filter: ExactFilterFunction | None = None,
) -> list[str]:
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
        num_words_after = len(word_list)
        print(f"Possible words reduced from {num_words_before} to {num_words_after}")
    return word_list


def inclusive_algorithm(word_list: list[str], answer: str, word_function: WordFunction, show_progress: bool = True) -> int:
    """
    Runs algorithm_step with the inclusive filter until it finds the answer.
    """
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
            f.inclusive_filter_by_feedback,
            show_progress,
            accepted_words,
            f.consistent_filter,
        )
        count += 1
    return count


def exclusive_algorithm(word_list: list[str], answer: str, word_function: WordFunction, show_progress: bool = True) -> int:
    """
    Solve using exact feedback partitions; ``word_function`` is retained for API
    compatibility with ``run_all`` and ``main.py`` but is intentionally ignored.
    """
    answer = answer.strip().upper()
    normalized_words = [word.strip().upper() for word in word_list]
    accepted_words = set(normalized_words)
    if answer not in accepted_words:
        raise ValueError(
            f"A resposta {answer!r} não está na lista de palavras candidatas. "
            "O algoritmo exclusivo só consegue encontrá-la se ela estiver nessa lista."
        )

    matrix, word_indices, word_key = _get_feedback_matrix(normalized_words)
    possible_answers = normalized_words.copy()
    possible_indices = list(range(len(normalized_words)))
    guessed_indices: set[int] = set()
    count = 0

    while True:
        if len(possible_answers) <= 2:
            guess = possible_answers[0]
            guess_index = word_indices[guess]
        elif count == 0:
            guess_index = _FIRST_GUESS_CACHE.get(word_key, -1)
            if guess_index < 0:
                guess_index = _choose_partition_guess(
                    possible_indices,
                    guessed_indices,
                    matrix,
                    word_key,
                )
                _FIRST_GUESS_CACHE[word_key] = guess_index
            if word_key == _INITIAL_WORDS_KEY and normalized_words[guess_index] != "SORIA":
                raise RuntimeError(
                    "O melhor primeiro palpite esperado para a lista atual é SORIA, "
                    f"mas foi calculado {normalized_words[guess_index]}."
                )
            guess = normalized_words[guess_index]
        else:
            guess_index = _choose_partition_guess(
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
        possible_answers = f.consistent_filter(
            possible_answers,
            guess,
            feedback,
        )
        possible_indices = [word_indices[word] for word in possible_answers]
        assert possible_answers, "O feedback eliminou todas as respostas possíveis."
        assert answer in possible_answers, "A resposta correta foi removida dos candidatos."
        if show_progress:
            f.reading_word_list(possible_answers, 15)
            print(
                f"Possible words reduced to {len(possible_answers)}"
            )

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
