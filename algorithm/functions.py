"""Shared word-list utilities and reusable feedback constraints."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import TypeAlias

from algorithm.termo_implementation import score_guess

Feedback: TypeAlias = tuple[
    list[tuple[str, int]],
    list[tuple[str, int]],
    list[tuple[str, int]],
]


def feedback_to_text(feedback: Feedback) -> str:
    """Convert feedback marks to the compact P/A/V representation."""
    marks = ["P"] * 5
    for _, position in feedback[1]:
        marks[position - 1] = "A"
    for _, position in feedback[2]:
        marks[position - 1] = "V"
    return "".join(marks)


def word_list_key(word_list: list[str]) -> str:
    """Return a stable fingerprint for an ordered word list."""
    digest = hashlib.sha256()
    for word in word_list:
        digest.update(word.strip().upper().encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def write_json_checkpoint(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a JSON evaluation checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f"{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as json_file:
            temporary_path = Path(json_file.name)
            json.dump(payload, json_file, ensure_ascii=False, indent=2)
            json_file.write("\n")
            json_file.flush()
            os.fsync(json_file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def summarize_evaluation_games(
    games: list[dict[str, object]],
) -> dict[str, object]:
    solved_games = [
        game for game in games if game.get("solved") is True
    ]
    distribution: dict[str, int] = {}
    for game in solved_games:
        attempts = game["attempts"]
        if isinstance(attempts, int) and not isinstance(attempts, bool):
            key = str(attempts)
            distribution[key] = distribution.get(key, 0) + 1
    return {
        "solved_games": len(solved_games),
        "unsolved_games": len(games) - len(solved_games),
        "distribution": distribution,
    }


def file_to_list(file_name: str) -> list[str]:
    """Read words from a file and normalize them to uppercase."""
    with open(file_name, "r", encoding="utf-8") as file:
        return [word for line in file if (word := line.strip().upper())]


def is_word_in_list(word: str, word_list: list[str]) -> bool:
    """Check whether a word appears in the list, ignoring case and whitespace."""
    normalized_word = word.strip().upper()
    normalized_words = {candidate.strip().upper() for candidate in word_list}
    return normalized_word in normalized_words


def reading_word_list(word_list: list[str], word_per_line: int) -> None:
    """Print the words in ``word_list`` with at most ``word_per_line`` per line."""
    if word_per_line <= 0:
        raise ValueError("word_per_line must be greater than zero.")

    for start in range(0, len(word_list), word_per_line):
        words = [
            word.strip().upper()
            for word in word_list[start:start + word_per_line]
        ]
        print(", ".join(words))


def count_words(word_list: list[str]) -> int:
    """Return the number of words in a list."""
    return len(word_list)


def filter_words_by_feedback(
    word_list: list[str],
    guess: str,
    feedback: Feedback,
) -> list[str]:
    """Keep words whose exact score for ``guess`` matches ``feedback``."""
    normalized_guess = guess.strip().upper()
    return [
        word
        for word in word_list
        if score_guess(word.strip().upper(), normalized_guess) == feedback
    ]


def black_letter(
    word_list: list[str],
    letter_pos_list: list[tuple[str, int]],
    yellow_positions: list[tuple[str, int]] | None = None,
    green_positions: list[tuple[str, int]] | None = None,
) -> list[str]:
    """Exclude excess occurrences of letters marked black."""
    normalized_black_letters = {
        letter.upper() for letter, _ in letter_pos_list
    }
    known_letter_counts: dict[str, int] = {}
    for letter, _ in (yellow_positions or []) + (green_positions or []):
        letter = letter.upper()
        known_letter_counts[letter] = known_letter_counts.get(letter, 0) + 1

    return [
        word
        for word in word_list
        if not any(
            word.upper().count(letter) > known_letter_counts.get(letter, 0)
            for letter in normalized_black_letters
        )
    ]


def yellow_letter(
    word_list: list[str],
    letter_pos_list: list[tuple[str, int]],
    green_positions: list[tuple[str, int]] | None = None,
) -> list[str]:
    """Require known letters and exclude yellow letters from their marked positions."""
    normalized_letter_positions = [
        (letter.upper(), position) for letter, position in letter_pos_list
    ]
    required_letter_counts: dict[str, int] = {}
    for letter, _ in letter_pos_list + (green_positions or []):
        letter = letter.upper()
        required_letter_counts[letter] = required_letter_counts.get(letter, 0) + 1

    filtered_words = []
    for word in word_list:
        normalized_word = word.upper()
        has_yellow_in_wrong_position = any(
            1 <= position <= len(normalized_word)
            and normalized_word[position - 1] == letter
            for letter, position in normalized_letter_positions
        )
        has_too_few_known_letters = any(
            normalized_word.count(letter) < count
            for letter, count in required_letter_counts.items()
        )
        if not has_yellow_in_wrong_position and not has_too_few_known_letters:
            filtered_words.append(word)
    return filtered_words


def green_letter(
    word_list: list[str],
    letter_pos_list: list[tuple[str, int]],
) -> list[str]:
    """Keep words matching all known green positions."""
    normalized_letter_positions = [
        (letter.upper(), position) for letter, position in letter_pos_list
    ]
    filtered_words = []
    for word in word_list:
        if all(
            1 <= position <= len(word)
            and word[position - 1].upper() == letter
            for letter, position in normalized_letter_positions
        ):
            filtered_words.append(word)
    return filtered_words
