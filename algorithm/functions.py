"""
functions.py funcitons for the algorithms
"""

def file_to_list(file_name: str) -> list[str]:
    """
    Reads a file and returns a list of words, each converted to uppercase.
    """
    words_list = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word = line.strip().upper()
            if word:
                words_list.append(word)
    return words_list

def filter_list(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    """
    Filters the words_list to keep only words that have the specified letter at the given position.
    """
    letter, position = letter_pos
    return [
        word
        for word in words_list
        if len(word) >= position and word[position - 1].upper() == letter.upper()
    ]

def letter_count(words_list: list[str]) -> dict[tuple[str, int], int]:
    """
    Counts the occurrences of each letter at each position in the given list of words.
    """
    letter_count_dict = {}
    for word in words_list:
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

def find_best_word_by_letter_position(words_list: list[str]) -> str:
    """
    Finds the best word based on letter position in the given list of words.
    """
    if not words_list:
        raise ValueError("Cannot find a best word in an empty word list.")

    word_length = len(words_list[0])
    selected_letters: dict[int, str] = {}
    candidates = words_list

    while len(selected_letters) < word_length:
        counts = letter_count(candidates)
        position_blacklist = [
            letter_pos
            for letter_pos in counts
            if letter_pos[1] in selected_letters
        ]
        used_letters = set(selected_letters.values())
        letter_blacklist = position_blacklist + [
            letter_pos
            for letter_pos in counts
            if letter_pos[0] in used_letters
        ]
        eligible_unused_letters = [
            letter_pos
            for letter_pos in counts
            if letter_pos not in letter_blacklist
        ]
        blacklist = letter_blacklist if eligible_unused_letters else position_blacklist
        letter, position = most_common_letter(counts, blacklist)
        selected_letters[position] = letter
        candidates = filter_list(candidates, (letter, position))

    return "".join(selected_letters[position] for position in range(1, word_length + 1))


def find_best_word_by_letter_frequency(words_list: list[str]) -> str:
    """"
    Finds the best word based on letter frequency in the given list of words.
    """
    if not words_list:
        raise ValueError("Cannot find a best word in an empty word list.")

    position_counts = letter_count(words_list)
    letter_counts: dict[str, int] = {}
    for (letter, _position), count in position_counts.items():
        letter_counts[letter] = letter_counts.get(letter, 0) + count

    candidates = [
        word.upper()
        for word in words_list
        if len(word) == 5 and len(set(word.upper())) == 5
    ]
    if not candidates:
        raise ValueError("No five-letter words with distinct letters found.")

    return max(
        candidates,
        key=lambda word: sum(letter_counts[letter] for letter in word),
    )

def black_letter(words_list: list[str], letter_list: list[str]) -> list[str]:
    """
    Filters the words_list to exclude words that contain any of the specified letters
    """
    normalized_letters = [letter.upper() for letter in letter_list]
    filtered_words = []
    for word in words_list:
        if not any(letter in normalized_letters for letter in word.upper()):
            filtered_words.append(word)
    return filtered_words

def yellow_letter(words_list: list[str], letter_pos_list: list[tuple[str, int]]) -> list[str]:
    """
    Filters the words_list to exclude words that contain any of the specified letters at the given positions
    """
    normalized_letter_positions = [(letter.upper(), position) for letter, position in letter_pos_list]
    filtered_words = []
    for word in words_list:
        if not any(1 <= position <= len(word) and word[position - 1].upper() == letter for letter, position in normalized_letter_positions):
            filtered_words.append(word)
    return filtered_words

def green_letter(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    """
    Filters the words_list to remove words that do not have the specified letter at the given position
    """
    letter, position = letter_pos
    filtered_words = []
    for word in words_list:
        if 1 <= position <= len(word) and word[position - 1].upper() == letter.upper():
            filtered_words.append(word)
    return filtered_words