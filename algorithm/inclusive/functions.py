"""Heuristics and feedback filters specific to the inclusive solver."""

from algorithm import functions as common
from algorithm.termo_implementation import score_guess

Feedback = common.Feedback


def letter_count(word_list: list[str]) -> dict[tuple[str, int], int]:
    """Count each letter at each position in a set of candidate words."""
    counts: dict[tuple[str, int], int] = {}
    for word in word_list:
        for index, letter in enumerate(word):
            key = letter.upper(), index + 1
            counts[key] = counts.get(key, 0) + 1
    return counts


def reading_letter_count(
    letter_count_dict: dict[tuple[str, int], int],
) -> None:
    """Print positional letter counts in descending order."""
    for (letter, position), count in sorted(
        letter_count_dict.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"Letter: {letter}, Position: {position}, Count: {count}")


def most_common_letter(
    letter_count_dict: dict[tuple[str, int], int],
    blacklist: list[tuple[str, int]],
) -> tuple[str, int]:
    """Return the most common positional letter not in ``blacklist``."""
    normalized_blacklist = {
        (letter.upper(), position) for letter, position in blacklist
    }
    filtered_counts = {
        key: count
        for key, count in letter_count_dict.items()
        if key not in normalized_blacklist
    }
    if not filtered_counts:
        raise ValueError("No eligible letters found.")
    return max(filtered_counts, key=filtered_counts.get)


def find_best_word_by_letter_position(
    word_list: list[str],
    allow_repeated_letters: bool = False,
) -> str:
    """Choose the word with the strongest positional letter counts."""
    if not word_list:
        raise ValueError("Cannot find a best word in an empty word list.")
    word_length = len(word_list[0])
    candidates = [word.upper() for word in word_list if len(word) == word_length]
    if not candidates:
        raise ValueError("No words of the expected length found.")
    if not allow_repeated_letters:
        distinct_candidates = [
            word for word in candidates if len(set(word)) == len(word)
        ]
        if distinct_candidates:
            candidates = distinct_candidates
    position_counts = letter_count(candidates)
    return max(
        candidates,
        key=lambda word: sum(
            position_counts.get((letter, position), 0)
            for position, letter in enumerate(word, start=1)
        ),
    )


def find_best_word_by_letter_frequency(
    word_list: list[str],
    allow_repeated_letters: bool = False,
) -> str:
    """Choose the word with the highest aggregate letter frequency."""
    if not word_list:
        raise ValueError("Cannot find a best word in an empty word list.")
    position_counts = letter_count(word_list)
    letter_counts: dict[str, int] = {}
    for (letter, _position), count in position_counts.items():
        letter_counts[letter] = letter_counts.get(letter, 0) + count
    candidates = [word.upper() for word in word_list if len(word) == 5]
    if not allow_repeated_letters:
        distinct_candidates = [
            word for word in candidates if len(set(word)) == len(word)
        ]
        if distinct_candidates:
            candidates = distinct_candidates
    if not candidates:
        raise ValueError("No five-letter words found.")
    return max(
        candidates,
        key=lambda word: sum(letter_counts[letter] for letter in word),
    )


def inclusive_filter_by_feedback(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """Apply the legacy black/yellow/green filters to feedback."""
    black_positions, yellow_positions, green_positions = feedback
    filtered_words = common.black_letter(
        word_list,
        black_positions,
        yellow_positions,
        green_positions,
    )
    filtered_words = common.yellow_letter(
        filtered_words,
        yellow_positions,
        green_positions,
    )
    return common.green_letter(filtered_words, green_positions)


def consistent_filter(
    word_list: list[str],
    guess: str,
    feedback: Feedback,
) -> list[str]:
    """Keep only words whose exact Wordle score matches the feedback."""
    normalized_guess = guess.strip().upper()
    return [
        word
        for word in word_list
        if score_guess(word.strip().upper(), normalized_guess) == feedback
    ]
