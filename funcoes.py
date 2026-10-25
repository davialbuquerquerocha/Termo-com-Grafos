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
    letters_pos = []
    letters_count = []
    for word in words_list:
        word_letters = list(word.strip())
        c = 1
        for letter in word_letters:
            if (letter, c) not in letters_pos:
                letters_pos.append((letter, c))
                letters_count.append((letter, c, 1))
            else:
                letters_count[letters_pos.index((letter, c))] = (letter, c, letters_count[letters_pos.index((letter, c))][2] + 1)
            c += 1
    return letters_count

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
    print(f"Best letters by position: {', '.join(map(str, selected_letters))}")
    return selected_letters
    # PROBLEMA LÓGICO A CONSERTAR, FUNÇÃO NUNCA IRÁ TENTAR PALAVRA COM LETRAS REPETIDAS

def black_letter(word_list: list[str], letter: str) -> list[str]:
    for word in word_list:
        if letter in word:
            word_list.remove(word)

def alg_yellow_letter(word_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    for word in word_list:
        if letter_pos[0] in word[letter_pos[1] - 1]:
            word_list.remove(word)
        if letter_pos[0] not in word:
            word_list.remove(word)

def res_yellow_letter():
    pass

def alg_green_letter(word_list: list[str], letter_pos: tuple[str, int]) -> list[str]:
    for word in word_list:
        if letter_pos[0] in word[letter_pos[1] - 1]:
            word_list.remove(word)

def res_green_letter():
    pass


    
