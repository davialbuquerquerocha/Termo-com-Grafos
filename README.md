# Termo-com-Grafos

Os algoritmos usam `dataset/words/termo_palavras_aceitas.txt` tanto como conjunto de
respostas possíveis quanto como conjunto de palpites. A lista separada de
soluções não é usada.

O algoritmo de partição escolhe palpites pela qualidade das partições de feedback
e pré-calcula uma matriz NumPy. O arquivo `.npy` é armazenado em
`dataset/cache/feedback-matrices/` e reutilizado enquanto a lista de palavras
não mudar.
Instale a dependência com `pip install -r requirements.txt`.

Execute os testes com `python -m unittest discover -s tests -v`. O launcher
central `main.py` seleciona o algoritmo; os comandos específicos de cada pacote
continuam disponíveis:

```text
python main.py partition evaluate --workers 4
python main.py entropy play --strategy groups
python main.py entropy simulate TERMO --strategy entropy
python main.py entropy evaluate --strategy groups --sample-size 200
python main.py inclusive --heuristic position
```

`python main.py` continua equivalente a `python main.py partition evaluate`.
A avaliação de partição usa o custo original de potência 2 e uma busca limitada
nos ramos ambíguos; ela não recalcula o algoritmo inclusivo. A busca compara o
pior número de tentativas do restante da política `p=2` e só instala um palpite
alternativo se todos os feedbacks do ramo couberem no limite de seis tentativas.
Esse fluxo fica em `algorithm/partition/evaluation.py`; `main.py` apenas
encaminha os argumentos para o pacote escolhido. O resultado JSON é gravado em
`dataset/results/resultados_partition_busca_limitada.json`. Ele registra a
identificação da lista, as configurações, o estado da avaliação, o resumo e,
para cada resposta, a sequência de palpites e feedbacks. Checkpoints são
atualizados atomicamente durante a execução, para que uma interrupção deixe o
último progresso válido. As respostas são processadas em paralelo usando por
padrão todos os processadores lógicos disponíveis. `--workers`, `--batch-size`
e `--output` personalizam essa avaliação. Para chamá-la diretamente em Python,
importe `run_all_answers` de `algorithm.partition.evaluation`.

O modo `inclusive` avalia todas as respostas com a heurística de posição
(padrão) ou frequência: use `--heuristic frequency` para escolher a segunda.
Ele usa um worker por padrão; `--workers` e `--output` permitem ajustar a
execução e o JSON gravado em `dataset/results/resultados_inclusive.json`, que
inclui a sequência de palpites e feedbacks por resposta e checkpoints seguros.

Os argumentos depois de `entropy` são encaminhados à CLI do pacote sem
alterações. Também é possível iniciar essa CLI diretamente conforme os exemplos
em `algorithm/entropy/info.txt`.

Os solvers ficam organizados em pacotes separados:

- `algorithm/inclusive/algorithm.py` contém o solver inclusivo e
  `algorithm/inclusive/functions.py` contém seus filtros e heurísticas.
  Consulte `algorithm/inclusive/info.txt` para exemplos de uso.
- `algorithm/partition/algorithm.py` contém o solver por partições e
  `algorithm/partition/functions.py` contém os auxiliares de matriz/partição e
  os filtros exclusivos legados. Consulte `algorithm/partition/info.txt` para
  os exemplos de execução e a avaliação em lote.
- `algorithm/entropy/` expõe o solver por entropia. Use `strategy="entropy"`
  para escolher apenas pela entropia dos palpites ou `strategy="groups"` para
  analisar recursivamente os grupos de feedback; `"deep"` continua disponível
  como alias. Inicie a CLI com
  `python -c "from algorithm.entropy.algorithm import main; main()" play --strategy groups`
  (ou `simulate`/`evaluate` no lugar de `play`). Consulte
  `algorithm/entropy/info.txt` para comandos, amostragem, perfilamento e
  arquivos de retomada.
  O comando `evaluate` salva os custos por resposta e o memo da busca em
  `dataset/cache/entropy/entropy_memo.sqlite3`, retomando resultados concluídos na execução
  seguinte. Use `--sample-size 200 --seed 2026` para medir uma amostra
  determinística mantendo todo o vocabulário de palpites; `--profile` mostra
  tempos e contagens internas, `--checkpoint-interval` controla a frequência
  de gravação, `--no-resume` recalcula a amostra selecionada e `--workers 4`
  avalia respostas em quatro processos da CPU (o padrão é serial). Cada worker
  usa um SQLite separado para o memo da busca; os resultados por resposta ficam
  no banco principal. Em `groups`, a busca do primeiro palpite também distribui
  candidatos entre os workers antes de avaliar as respostas; a recursão dentro
  de cada candidato continua serial e as etapas não criam pools aninhados. Os
  caches em memória usam LRU limitado; os estados finalizados da busca são
  gravados no SQLite a cada 1.000 estados.
  Cada avaliação também salva em `dataset/results/` um JSON chamado
  `entropy_games_<estrategia>_<AAAAMMDD_HHMMSS>.json`, com a
  resposta, cada palpite e o feedback observado naquele jogo, atualizado a
  cada checkpoint.
  As sequências são simuladas individualmente para cada resposta, nunca
  copiadas de palavras com caminhos parecidos. Ao final, o JSON inclui as
  métricas agregadas; se interrompida, fica marcado como incompleto. Ao retomar,
  jogos antigos sem sequência registrada são simulados novamente.
- `algorithm/evo_search/` ajusta pesos por busca evolutiva. Consulte
  `algorithm/evo_search/info.txt` para os comandos, arquivos gerados e
  parâmetros ativos.
- `algorithm/functions.py` reúne tipos, utilitários de listas e restrições
  genéricas de feedback compartilhadas. A pontuação continua em
  `algorithm/termo_implementation.py`.