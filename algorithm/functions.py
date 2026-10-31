"""Shared word-list utilities and reusable feedback constraints."""

Feedback = tuple[
    list[tuple[str, int]],
    list[tuple[str, int]],
    list[tuple[str, int]],
]


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


def black_letter(
    word_list: list[str],
    letter_pos_list: list[tuple[str, int]],
    yellow_positions: list[tuple[str, int]] | None = None,
    green_positions: list[tuple[str, int]] | None = None,
) -> list[str]:
    """Exclude excess occurrences of letters marked black."""
    normalized_black_letters = {
        letter.upper() for letter, _position in letter_pos_list
    }
    known_letter_counts: dict[str, int] = {}
    for letter, _position in (yellow_positions or []) + (green_positions or []):
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
    for letter, _position in letter_pos_list + (green_positions or []):
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
