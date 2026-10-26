"""
algo1.py real human-made implementation
"""

def file_to_list(file_name: str) -> list[str]:
    words_list = []
    with open(file_name, 'r', encoding='utf-8') as file:
        for line in file:
            word = line.strip().upper()
            if word:
                words_list.append(word)
    return words_list

def filter_list(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    letter, position = letter_pos
    return [
        word
        for word in words_list
        if len(word) >= position and word[position - 1].upper() == letter.upper()
    ]

def letter_count(words_list: list[str]) -> dict[tuple[str, int], int]:
    letter_count_dict = {}
    for word in words_list:
        for index, letter in enumerate(word):
            key = (letter.upper(), index + 1)
            letter_count_dict[key] = letter_count_dict.get(key, 0) + 1
    return letter_count_dict

def reading_letter_count(letter_count_dict: dict[tuple[str, int], int]) -> None:
    for (letter, position), count in sorted(letter_count_dict.items(), key=lambda x: (-x[1], x[0])):
        print(f"Letter: {letter}, Position: {position}, Count: {count}")

def most_common_letter(letter_count_dict: dict[tuple[str, int], int], blacklist: list[tuple[str, int]]) -> tuple[str, int]:
    normalized_blacklist = {(letter.upper(), position) for letter, position in blacklist}
    filtered_dict = {k: v for k, v in letter_count_dict.items() if k not in normalized_blacklist}
    if not filtered_dict:
        raise ValueError("No eligible letters found.")
    return max(filtered_dict, key=filtered_dict.get)

def find_best_word_by_letter_position(words_list: list[str]) -> str:
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
    normalized_letters = [letter.upper() for letter in letter_list]
    return [word for word in words_list if not any(letter in word.upper() for letter in normalized_letters)]

def alg_yellow_letter(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    pass

def res_yellow_letter(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    pass

def alg_green_letter(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    pass

def res_green_letter(words_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    pass





words_list = file_to_list('termo_palavras_aceitas.txt')
words_list = black_letter(words_list, ['a', 'R'])
reading_letter_count(letter_count(words_list))
print(find_best_word_by_letter_frequency(words_list))



