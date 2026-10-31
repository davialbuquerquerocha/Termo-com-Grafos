"""Legacy feedback filters specific to the partition solver."""

from algorithm import functions as common

Feedback = common.Feedback
VOWELS = frozenset("AEIOU")


def exclusive_filter_by_feedback(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """Legacy filter that treats green letters as misplaced letters."""
    black_positions, yellow_positions, green_positions = feedback
    known_non_black_positions = yellow_positions + green_positions
    filtered_words = common.black_letter(
        word_list,
        black_positions,
        yellow_positions,
        green_positions,
    )
    return common.yellow_letter(filtered_words, known_non_black_positions)


def exclusive_filter_by_feedback_preserving_green_vowels(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """Legacy exclusive filter that permits green vowels in place."""
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
    filtered_words = common.black_letter(
        word_list,
        black_positions,
        yellow_positions,
        green_positions,
    )
    return common.yellow_letter(
        filtered_words,
        yellow_positions + green_consonants,
        green_vowels,
    )


def exclusive_filter_by_feedback_ignoring_vowels(
    word_list: list[str],
    feedback: Feedback,
) -> list[str]:
    """Legacy exclusive filter using only consonant feedback."""
    black_positions, yellow_positions, green_positions = feedback
    consonant_feedback = (
        [
            (letter, position)
            for letter, position in black_positions
            if letter.upper() not in VOWELS
        ],
        [
            (letter, position)
            for letter, position in yellow_positions
            if letter.upper() not in VOWELS
        ],
        [
            (letter, position)
            for letter, position in green_positions
            if letter.upper() not in VOWELS
        ],
    )
    return exclusive_filter_by_feedback(word_list, consonant_feedback)
