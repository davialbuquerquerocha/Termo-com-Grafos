#!/usr/bin/env python3
"""One-shot Wordle checker.

Given a word list file (one word per line), the secret answer and a single
guess, the program prints a tuple containing three lists of (letter, position)
tuples, ordered as black, yellow and green.

Standard Wordle scoring is used: green marks are assigned first and consume
one occurrence of the letter in the answer; the remaining letters can then be
yellow while there are unconsumed occurrences left, otherwise black. This
makes duplicated letters behave exactly like the real game.

Only the guess is validated: it must be made of letters only, have the same
length as the answer and be present in the word list, otherwise an
InvalidWordError is raised. The answer is taken as given (it is the secret
word of the round).

CLI usage:
    python program.py <wordlist_file> <answer> "<guess>"

Examples:
    $ python program.py textfile1.txt AIDED "FIRST"
    ([('F', 1), ('R', 3), ('S', 4), ('T', 5)], [], [('I', 2)])

    $ python program.py textfile1.txt AIDED "ASDFW"
    InvalidWordError: invalid guess 'ASDFW': word is not in the word list

    $ python program.py textfile1.txt AIDED "AID"
    InvalidWordError: invalid guess 'AID': expected 5 letters, got 3

Library usage:
    from program import evaluate_guess, load_wordlist

    words = load_wordlist("textfile1.txt")
    evaluate_guess("AIDED", "FIRST", words)
"""

from __future__ import annotations

import sys


class InvalidWordError(ValueError):
    """Raised when a word is not valid for the game."""


def load_wordlist(path: str) -> set[str]:
    """Load the valid words from ``path`` (one word per line, case-insensitive)."""
    words: set[str] = set()
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            word = line.strip().upper()
            if word:
                words.add(word)
    return words


def score_guess(
    answer: str,
    guess: str,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
    """Score ``guess`` against ``answer`` using standard Wordle rules.

    Returns ``(black, yellow, green)`` lists of ``(letter, position)`` tuples.
    Positions are 1-based.
    """
    if len(answer) != len(guess):
        raise ValueError("answer and guess must have the same length")

    remaining: dict[str, int] = {}
    for letter in answer:
        remaining[letter] = remaining.get(letter, 0) + 1

    marks: list[int] = [0] * len(guess)

    # First pass: exact matches are green and consume one occurrence
    # of that letter in the answer.
    for index, (guess_letter, answer_letter) in enumerate(zip(guess, answer)):
        if guess_letter == answer_letter:
            marks[index] = 2
            remaining[guess_letter] -= 1

    # Second pass: misplaced letters are yellow while there are
    # unconsumed occurrences left, otherwise black.
    for index, guess_letter in enumerate(guess):
        if marks[index] == 2:
            continue
        if remaining.get(guess_letter, 0) > 0:
            marks[index] = 1
            remaining[guess_letter] -= 1

    black = [(letter, index + 1) for index, (mark, letter) in enumerate(zip(marks, guess)) if mark == 0]
    yellow = [(letter, index + 1) for index, (mark, letter) in enumerate(zip(marks, guess)) if mark == 1]
    green = [(letter, index + 1) for index, (mark, letter) in enumerate(zip(marks, guess)) if mark == 2]
    return black, yellow, green


def evaluate_guess(
    answer: str,
    guess: str,
    wordlist: set[str],
) -> tuple[list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
    """Validate ``guess`` and score it against ``answer``.

    Raises:
        InvalidWordError: if the guess is not made of letters, does not have
            the same length as the answer, or is not present in the word list.
    """
    answer = answer.strip().upper()
    guess = guess.strip().upper()

    if not answer.isalpha():
        raise InvalidWordError(f"invalid answer word: {answer!r}")
    if not guess.isalpha():
        raise InvalidWordError(f"invalid guess {guess!r}: only letters are allowed")
    if len(guess) != len(answer):
        raise InvalidWordError(
            f"invalid guess {guess!r}: expected {len(answer)} letters, got {len(guess)}"
        )
    if guess not in wordlist:
        raise InvalidWordError(f"invalid guess {guess!r}: word is not in the word list")

    return score_guess(answer, guess)


def main(argv: list[str]) -> None:
    if len(argv) != 4:
        raise SystemExit(f"usage: {argv[0]} <wordlist_file> <answer> <guess>")

    wordlist_path, answer, guess = argv[1], argv[2], argv[3]
    wordlist = load_wordlist(wordlist_path)
    print(evaluate_guess(answer, guess, wordlist))


if __name__ == "__main__":
    main(sys.argv)
