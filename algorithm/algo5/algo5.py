WEIGHTS = open("pesos.csv", 'w')
LETTER_POSITIONS = open("../../dataset/letters_position.csv", 'r')
lowercase_alphabet = [].append(chr(i) for i in range(ord('a'), ord('z') + 1))
print(lowercase_alphabet)

#class letter:
#    def __init__(self):
#    self.black  = [1, 2, 3, 4, 5]
#    self.yellow = [1, 2, 3, 4, 5]
#    self.green  = [1, 2, 3, 4, 5]