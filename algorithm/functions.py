"""
functions.py funcitons for the algorithms
"""

if __package__:
    from .termo_implementation import score_guess
else:
    from termo_implementation import score_guess

Feedback = tuple[list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]
VOWELS = frozenset("AEIOU")

def file_to_list(file_name: str) -> list[str]:
    """
    Reads a file and returns a list of words, each converted to uppercase.
    """
    word_list = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word = line.strip().upper()
            if word:
                word_list.append(word)
    return word_list

def is_word_in_list(word: str, word_list: list[str]) -> bool:
    """
    Checks whether a word is in the list, ignoring case and surrounding whitespace.
    """
    normalized_word = word.strip().upper()
    normalized_words = {candidate.strip().upper() for candidate in word_list}
    return normalized_word in normalized_words

def reading_word_list(word_list: list[str], word_per_line: int):
    """
    Prints the words in the word_list line by line
    """
    if word_per_line <= 0:
        raise ValueError("word_per_line must be greater than zero.")

    for start in range(0, len(word_list), word_per_line):
        words = [word.strip().upper() for word in word_list[start:start + word_per_line]]
        print(", ".join(words))

def count_words(word_list: list[str]) -> int:
    """
    Returns the number of words in the list.
    """
    return len(word_list)

def letter_count(word_list: list[str]) -> dict[tuple[str, int], int]:
    """
    Counts the occurrences of each letter at each position in the given list of words.
    """
    letter_count_dict = {}
    for word in word_list:
        for index, letter in enumerate(word):
            key = (letter.upper(), index + 1)
            letter_count_dict[key] = letter_count_dict.get(key, 0) + 1
    return letter_count_dict

def reading_letter_count(letter_count_dict: dict[tuple[str, int], int]) -> None:
    """
    Prints the letter count dictionary in a readable format.
    """
    for (letter, position), count in sorted(letter_count_dict.items(), key=lambda x: (-x[1], x[0])):
        print(f"Letter: {letter}, Position: {position}, Count: {count}")

def most_common_letter(letter_count_dict: dict[tuple[str, int], int], blacklist: list[tuple[str, int]]) -> tuple[str, int]:
    """
    Finds the most common letter in the letter_count_dict that is not in the blacklist.
    """
    normalized_blacklist = {(letter.upper(), position) for letter, position in blacklist}
    filtered_dict = {k: v for k, v in letter_count_dict.items() if k not in normalized_blacklist}
    if not filtered_dict:
        raise ValueError("No eligible letters found.")
    return max(filtered_dict, key=filtered_dict.get)

def find_best_word_by_letter_position(word_list: list[str], allow_repeated_letters: bool = False) -> str:
    """
    Finds the best word by letter position.

    If repeated letters are not allowed, words without repeats are preferred;
    words with repeats are considered only when no distinct-letter word exists.
    """
    if not word_list:
        raise ValueError("Cannot find a best word in an empty word list.")
    word_length = len(word_list[0])
    candidates = [word.upper() for word in word_list if len(word) == word_length]
    if not candidates:
        raise ValueError("No words of the expected length found.")
    if not allow_repeated_letters:
        distinct_letter_candidates = [word for word in candidates if len(set(word)) == len(word)]
        if distinct_letter_candidates:
            candidates = distinct_letter_candidates
    position_counts = letter_count(candidates)
    return max(candidates, key=lambda word: sum(position_counts.get((letter, position), 0) for position, letter in enumerate(word, start=1)))

def find_best_word_by_letter_frequency(word_list: list[str], allow_repeated_letters: bool = False) -> str:
    """
    Finds the best word by letter frequency.

    If repeated letters are not allowed, words without repeats are preferred;
    words with repeats are considered only when no distinct-letter word exists.
    """
    if not word_list:
        raise ValueError("Cannot find a best word in an empty word list.")
    position_counts = letter_count(word_list)
    letter_counts: dict[str, int] = {}
    for (letter, _position), count in position_counts.items():
        letter_counts[letter] = letter_counts.get(letter, 0) + count
    candidates = [word.upper() for word in word_list if len(word) == 5]
    if not allow_repeated_letters:
        distinct_letter_candidates = [word for word in candidates if len(set(word)) == len(word)]
        if distinct_letter_candidates:
            candidates = distinct_letter_candidates
    if not candidates:
        raise ValueError("No five-letter words found.")
    return max(candidates, key=lambda word: sum(letter_counts[letter] for letter in word))

def black_letter(word_list: list[str], letter_pos_list: list[tuple[str, int]], yellow_positions: list[tuple[str, int]] | None = None, green_positions: list[tuple[str, int]] | None = None) -> list[str]:
    """
    Filters out black letters beyond their known yellow and green occurrences.
    """
    normalized_black_letters = {letter.upper() for letter, _position in letter_pos_list}
    known_letter_counts: dict[str, int] = {}
    for letter, _position in (yellow_positions or []) + (green_positions or []):
        letter = letter.upper()
        known_letter_counts[letter] = known_letter_counts.get(letter, 0) + 1

    filtered_words = []
    for word in word_list:
        normalized_word = word.upper()
        has_excess_black_letter = any(
            normalized_word.count(letter) > known_letter_counts.get(letter, 0)
            for letter in normalized_black_letters
        )
        if not has_excess_black_letter:
            filtered_words.append(word)
    return filtered_words


def yellow_letter(word_list: list[str], letter_pos_list: list[tuple[str, int]], green_positions: list[tuple[str, int]] | None = None) -> list[str]:
    """
    Filters out yellow letters in their marked positions and requires their known occurrences.
    """
    normalized_letter_positions = [(letter.upper(), position) for letter, position in letter_pos_list]
    required_letter_counts: dict[str, int] = {}
    for letter, _position in letter_pos_list + (green_positions or []):
        letter = letter.upper()
        required_letter_counts[letter] = required_letter_counts.get(letter, 0) + 1

    filtered_words = []
    for word in word_list:
        normalized_word = word.upper()
        has_yellow_in_wrong_position = any(
            1 <= position <= len(normalized_word) and normalized_word[position - 1] == letter
            for letter, position in normalized_letter_positions
        )
        has_too_few_known_letters = any(
            normalized_word.count(letter) < count
            for letter, count in required_letter_counts.items()
        )
        if not has_yellow_in_wrong_position and not has_too_few_known_letters:
            filtered_words.append(word)
    return filtered_words

def green_letter(word_list: list[str], letter_pos_list: list[tuple[str, int]]) -> list[str]:
    """
    Filters the word_list to keep only words that have all specified letters
    at their given positions.
    """
    normalized_letter_positions = [(letter.upper(), position) for letter, position in letter_pos_list]
    filtered_words = []
    for word in word_list:
        matches_all_positions = True
        for letter, position in normalized_letter_positions:
            if not (1 <= position <= len(word) and word[position - 1].upper() == letter):
                matches_all_positions = False
                break
        if matches_all_positions:
            filtered_words.append(word)
    return filtered_words


def inclusive_filter_by_feedback(word_list: list[str], feedback: Feedback) -> list[str]:
    """
    Filters words using feedback ordered as black, yellow, and green positions.
    """
    black_positions, yellow_positions, green_positions = feedback
    filtered_words = black_letter(word_list, black_positions, yellow_positions, green_positions)
    filtered_words = yellow_letter(filtered_words, yellow_positions, green_positions)
    filtered_words = green_letter(filtered_words, green_positions)
    return filtered_words

def consistent_filter(
    word_list: list[str],
    guess: str,
    feedback: Feedback,
) -> list[str]:
    """Keep only words whose exact Wordle score matches the observed feedback."""
    normalized_guess = guess.strip().upper()
    return [
        word for word in word_list
        if score_guess(word.strip().upper(), normalized_guess) == feedback
    ]

def exclusive_filter_by_feedback(word_list: list[str], feedback: Feedback) -> list[str]:
    """
    Filters guesses by treating green letters as yellow letters.
    """
    black_positions, yellow_positions, green_positions = feedback
    known_non_black_positions = yellow_positions + green_positions
    filtered_words = black_letter(word_list, black_positions, yellow_positions, green_positions)
    filtered_words = yellow_letter(filtered_words, known_non_black_positions)
    return filtered_words

def exclusive_filter_by_feedback_preserving_green_vowels(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """
    Filters guesses exclusively while allowing green vowels in their positions.
    """
    black_positions, yellow_positions, green_positions = feedback
    green_consonants = [
        (letter, position)
        for letter, position in green_positions
        if letter.upper() not in VOWELS
    ]
    green_vowels = [
        (letter, position)
        for letter, position in green_positions
        if letter.upper() in VOWELS
    ]
    filtered_words = black_letter(
        word_list,
        black_positions,
        yellow_positions,
        green_positions,
    )
    return yellow_letter(
        filtered_words,
        yellow_positions + green_consonants,
        green_vowels,
    )

def exclusive_filter_by_feedback_ignoring_vowels(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """
    Applies the exclusive filter using only consonant feedback.
    """
    black_positions, yellow_positions, green_positions = feedback
    consonant_feedback = (
        [(letter, position) for letter, position in black_positions if letter.upper() not in VOWELS],
        [(letter, position) for letter, position in yellow_positions if letter.upper() not in VOWELS],
        [(letter, position) for letter, position in green_positions if letter.upper() not in VOWELS],
    )
    return exclusive_filter_by_feedback(word_list, consonant_feedback)
