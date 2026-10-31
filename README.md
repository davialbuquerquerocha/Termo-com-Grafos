# Termo-com-Grafos

Os algoritmos usam `dataset/termo_palavras_aceitas.txt` tanto como conjunto de
respostas possíveis quanto como conjunto de palpites. A lista separada de
soluções não é usada.

O algoritmo exclusivo escolhe palpites pela qualidade das partições de feedback
e pré-calcula uma matriz NumPy. O arquivo `.npy` é armazenado em
`%LOCALAPPDATA%\Termo` e reutilizado enquanto a lista de palavras não mudar.
Instale a dependência com `pip install -r requirements.txt`.

Execute os testes com `python -m unittest discover -s tests -v`. A simulação de
`main.py` mantém as colunas `answer, algorithm, word_function, attempts, solved`
no CSV.