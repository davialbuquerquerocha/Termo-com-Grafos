"""Fixa a primeira palavra e procura a melhor segunda palavra.

Colocar este arquivo na RAIZ do projeto (Termo-com-Grafos) e rodar de lá:
    python segunda_palavra.py
"""
import numpy as np

from algorithm.entropy import algorithm as alg
from algorithm.entropy import functions as helpers

PRIMEIRA = "CARTO"        # exatamente como está escrita no dataset (maiúsculas)
TOP = 10                  # quantas segundas palavras "únicas" mostrar
ARQUIVO_SOLUCOES = None   # ex.: "solucoes.txt" (uma palavra por linha) p/ restringir às 1442

if ARQUIVO_SOLUCOES:
    with open(ARQUIVO_SOLUCOES, encoding="utf-8") as f:
        candidatos = alg._normalize_candidates(f.read().splitlines())
else:
    candidatos = alg._load_answers()

ctx = alg._search_context(candidatos)
guesses, word_indices, matrix, _ = ctx
NCODES = alg.partition_functions._FEEDBACK_PATTERN_COUNT   # 243
VITORIA = NCODES - 1                                       # tudo verde

if PRIMEIRA not in word_indices:
    raise SystemExit(f"{PRIMEIRA!r} não está no dataset (confira maiúsculas/acentos).")

N = len(candidatos)
idx_c = np.fromiter((word_indices[w] for w in candidatos), dtype=np.intp, count=N)

# --- feedback da primeira palavra para cada candidata ---
codes1 = matrix[word_indices[PRIMEIRA], idx_c].astype(np.int64)
grupos = {}
for w, c in zip(candidatos, codes1):
    grupos.setdefault(int(c), []).append(w)
print(f"{PRIMEIRA}: {len(grupos)} configurações ocorrem, {N} candidatas")

# --- A) melhor segunda palavra ÚNICA (mesma para qualquer feedback) ---
# score = ||n||^2 / N = nº esperado de candidatas restantes após os 2 palpites
linhas = np.fromiter((word_indices[w] for w in guesses), dtype=np.intp, count=len(guesses))
sub = matrix[np.ix_(linhas, idx_c)]            # (palpites x candidatas)
score = np.empty(len(guesses))
for g in range(len(guesses)):
    cont = np.bincount(codes1 * NCODES + sub[g])
    score[g] = (cont.astype(np.int64) ** 2).sum() / N

print(f"\nMelhores segundas palavras ÚNICAS depois de {PRIMEIRA} (menor = melhor):")
for g in np.argsort(score, kind="stable")[:TOP]:
    print(f"  {guesses[g]}   candidatas restantes esperadas: {score[g]:.2f}")

# --- B) melhor segunda palavra PARA CADA feedback (busca recursiva dos colegas) ---
# depth=0 faz a busca mais ampla; use 1 para reproduzir exatamente o jogo deles.
total = 1.0
print(f"\nMelhor segunda palavra para cada feedback de {PRIMEIRA}:")
for cod, grupo in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
    if cod == VITORIA:
        continue
    gi, custo = helpers._best_move(grupo, 0, ctx)
    total += len(grupo) / N * custo
    print(f"  config {cod:3d}: {len(grupo):4d} candidatas -> {guesses[gi]}   (custo esperado {custo:.2f})")

print(f"\nCusto esperado total começando com {PRIMEIRA}: {total:.3f} palpites")
