# Termo-com-Grafos

Os algoritmos usam `dataset/termo_palavras_aceitas.txt` tanto como conjunto de
respostas possíveis quanto como conjunto de palpites. A lista separada de
soluções não é usada.

O algoritmo de partição escolhe palpites pela qualidade das partições de feedback
e pré-calcula uma matriz NumPy. O arquivo `.npy` é armazenado em `dataset/` e
reutilizado enquanto a lista de palavras não mudar.
Instale a dependência com `pip install -r requirements.txt`.

Execute os testes com `python -m unittest discover -s tests -v`. A simulação de
`main.py` calcula apenas o algoritmo de partição com o custo original de potência
2 e uma busca limitada nos ramos ambíguos; ela não recalcula o algoritmo
inclusivo. A busca compara o pior número de tentativas do restante da política
`p=2` e só instala um palpite alternativo se todos os feedbacks do ramo couberem
no limite de seis tentativas. O resultado é gravado em
`dataset/resultados_partition_busca_limitada.csv`, mantendo as colunas
`answer, algorithm, word_function, attempts, solved`. As respostas são
processadas em paralelo usando por padrão todos os processadores lógicos
disponíveis; o CSV é escrito pelo processo principal e mantém a ordem original.
Para limitar workers ao chamar a função, use
`run_all_answers(words, output_path, max_workers=4)`.

Os solvers ficam organizados em pacotes separados:

- `algorithm/inclusive/algorithm.py` contém o solver inclusivo e
  `algorithm/inclusive/functions.py` contém seus filtros e heurísticas.
- `algorithm/partition/algorithm.py` contém o solver por partições e
  `algorithm/partition/functions.py` contém os auxiliares de matriz/partição e
  os filtros exclusivos legados.
- `algorithm/functions.py` reúne tipos, utilitários de listas e restrições
  genéricas de feedback compartilhadas. A pontuação continua em
  `algorithm/termo_implementation.py`.