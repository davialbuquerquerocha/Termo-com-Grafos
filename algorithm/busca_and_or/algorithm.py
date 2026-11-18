"""Solver com garantia de no máximo 6 palpites (busca AND-OR com memoização).

Duas listas possíveis
---------------------
* TOTAL:    respostas = palavras aceitas; palpites = palavras aceitas.
* REDUZIDA: respostas = soluções possíveis; palpites = palavras aceitas.

Ideia central
-------------
Perguntamos, para cada grupo de candidatas S e tentativas d:
    "Existe um palpite que, para TODOS os feedbacks possíveis, deixa um
     grupo que ainda dá para resolver com d-1 tentativas?"
A heurística só define a ORDEM dos palpites testados. A garantia vem da busca.

Uso:
    python -m algorithm.busca_and_or.algorithm
    python -m algorithm.busca_and_or.algorithm --lista reduzida --modo todas --estatisticas detalhadas
    python -m algorithm.busca_and_or.algorithm --lista total --modo amostra --amostra 300
    python -m algorithm.busca_and_or.algorithm --lista reduzida --modo palavra --palavra casal
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import random
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

N_PADROES = 3 ** 5
MAX_TENTATIVAS = 6
TODOS = 10 ** 9                       # "largura infinita"
LARGURAS = (3, 8, 24, 80, 300, TODOS)

RAIZ = Path(__file__).resolve().parents[2]
DATASET = RAIZ / "dataset"
ARQ_RESPOSTAS = DATASET / "termo_solucoes_possiveis.txt"
ARQ_ACEITAS = DATASET / "termo_palavras_aceitas.txt"


# ======================================================================
# 0) Leitura e montagem das listas
# ======================================================================
def ler_lista(caminho: Path) -> list[str]:
    if not caminho.exists():
        sys.exit(f"Arquivo não encontrado: {caminho}")
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    return list(dict.fromkeys(l.strip().lower() for l in linhas if l.strip()))


def montar_listas(respostas: list[str], aceitas: list[str]) -> tuple[list[str], list[str]]:
    """Devolve (respostas, palpites). Os palpites começam pelas respostas, na
    mesma ordem, então o índice de uma palavra vale para resposta e palpite."""
    respostas = list(dict.fromkeys(respostas))
    palpites = list(respostas)
    vistos = set(palpites)
    for w in aceitas:
        if w not in vistos:
            palpites.append(w)
            vistos.add(w)
    return respostas, palpites


# ======================================================================
# 1) Matriz de feedback: M[g, a] = código 0..242 do palpite g contra a resposta a
# ======================================================================
def calcular_matriz(palpites: list[str], respostas: list[str]) -> np.ndarray:
    alfabeto = sorted(set("".join(palpites)) | set("".join(respostas)))
    indice = {c: i for i, c in enumerate(alfabeto)}
    L = len(alfabeto)

    A = np.array([[indice[c] for c in w] for w in respostas], dtype=np.int16)
    G = np.array([[indice[c] for c in w] for w in palpites], dtype=np.int16)
    na = len(respostas)

    contagem = np.zeros((L, na), dtype=np.int8)   # contagem[letra, resposta]
    for p in range(5):
        np.add.at(contagem, (A[:, p], np.arange(na)), 1)

    matriz = np.empty((len(palpites), na), dtype=np.uint8)
    pesos = [3 ** p for p in range(5)]
    for gi in range(len(palpites)):
        g = G[gi]
        verde = A == g                              # (na, 5)
        resto = contagem.copy()
        for p in range(5):
            resto[g[p]] -= verde[:, p]
        codigo = np.zeros(na, dtype=np.int32)
        for p in range(5):
            amarelo = (~verde[:, p]) & (resto[g[p]] > 0)
            resto[g[p]] -= amarelo
            codigo += (2 * verde[:, p] + amarelo) * pesos[p]
        matriz[gi] = codigo
    return matriz


def obter_matriz(palpites: list[str], respostas: list[str],
                 pasta_cache: Path | None) -> np.ndarray:
    if pasta_cache is not None and pasta_cache.is_dir():
        texto = "\n".join(palpites) + "\n#\n" + "\n".join(respostas)
        h = hashlib.md5(texto.encode()).hexdigest()[:10]
        arquivo = pasta_cache / f"matriz_busca_and_or_{h}.npy"
        if arquivo.exists():
            return np.load(arquivo)
        m = calcular_matriz(palpites, respostas)
        np.save(arquivo, m)
        return m
    return calcular_matriz(palpites, respostas)


# ======================================================================
# 2) Contagem dos grupos de cada palpite
# ======================================================================
def contar_grupos(matriz: np.ndarray, S: np.ndarray, bloco: int = 256) -> np.ndarray:
    """counts[g, f] = quantas candidatas de S dão o feedback f ao palpite g."""
    n = matriz.shape[0]
    counts = np.empty((n, N_PADROES), dtype=np.int32)
    desloc = (np.arange(bloco, dtype=np.int32) * N_PADROES)[:, None]
    for ini in range(0, n, bloco):
        fim = min(ini + bloco, n)
        sub = matriz[ini:fim][:, S].astype(np.int32) + desloc[: fim - ini]
        flat = np.bincount(sub.ravel(), minlength=(fim - ini) * N_PADROES)
        counts[ini:fim] = flat.reshape(fim - ini, N_PADROES)
    return counts


# ======================================================================
# 3) Busca AND-OR com garantia
# ======================================================================
class Contexto:
    def __init__(self, respostas: list[str], palpites: list[str],
                 pasta_cache: Path | None = None):
        self.respostas = respostas
        self.palpites = palpites
        self.matriz = obter_matriz(palpites, respostas, pasta_cache)
        self.ok: dict[bytes, tuple[int, int]] = {}
        self.falha: dict[tuple[bytes, int], int] = {}


def _falhou(ctx: Contexto, chave: bytes, d: int, K: int) -> bool:
    return any(ctx.falha.get((chave, k), 0) >= d for k in LARGURAS if k >= K)


def resolver(ctx: Contexto, S: np.ndarray, d: int, K: int = TODOS) -> int | None:
    """S = índices das respostas ainda candidatas. Devolve o índice de um palpite
    que resolve todas as candidatas de S em no máximo d tentativas, ou None."""
    m = len(S)
    if d < 1:
        return None
    if m == 1:
        return int(S[0])
    if d == 1:
        return None

    chave = S.tobytes()
    achado = ctx.ok.get(chave)
    if achado is not None and achado[0] <= d:
        return achado[1]
    if _falhou(ctx, chave, d, K):
        return None

    if m == 2:
        ctx.ok[chave] = (2, int(S[0]))
        return int(S[0])

    M = ctx.matriz
    counts = contar_grupos(M, S)
    maior = counts.max(axis=1)
    eh_cand = np.zeros(M.shape[0], dtype=bool)
    eh_cand[S] = True

    if d == 2:
        bons = np.flatnonzero(maior == 1)
        if len(bons):
            melhor = bons[np.argmax(eh_cand[bons])]
            ctx.ok[chave] = (2, int(melhor))
            return int(melhor)
        ctx.falha[(chave, TODOS)] = max(ctx.falha.get((chave, TODOS), 0), 2)
        return None

    k = (counts > 0).sum(axis=1)
    soma_q = (counts.astype(np.int64) ** 2).sum(axis=1)
    ordem = np.lexsort((soma_q, ~eh_cand, -k, maior))

    for g in ordem[:K]:
        if maior[g] >= m:
            break
        fb = M[g, S]
        por_fb = np.argsort(fb, kind="stable")
        fb_ord = fb[por_fb]
        cortes = np.flatnonzero(np.diff(fb_ord)) + 1
        grupos = [G for G in np.split(S[por_fb], cortes) if len(G) > 1]
        grupos.sort(key=len, reverse=True)
        if all(resolver(ctx, G, d - 1, K) is not None for G in grupos):
            ctx.ok[chave] = (d, int(g))
            return int(g)

    ctx.falha[(chave, K)] = max(ctx.falha.get((chave, K), 0), d)
    return None


def resolver_garantido(ctx: Contexto, S: np.ndarray, d: int) -> int | None:
    for K in LARGURAS:
        g = resolver(ctx, S, d, K)
        if g is not None:
            return g
    return None


# ======================================================================
# 4) Partida completa
# ======================================================================
_CACHE: dict[str, Contexto] = {}


def _contexto(respostas: list[str], aceitas: list[str], lista: str) -> Contexto:
    if lista not in _CACHE:
        novas_respostas, novos_palpites = montar_listas(respostas, aceitas)
        _CACHE[lista] = Contexto(novas_respostas, novos_palpites, DATASET)
    return _CACHE[lista]


def codigo_para_cores(codigo: int) -> str:
    cores = ""
    for p in range(5):
        v = (int(codigo) // 3 ** p) % 3
        cores += "🟩" if v == 2 else "🟨" if v == 1 else "⬛"
    return cores


def jogar_partida(respostas: list[str], aceitas: list[str], answer: str,
                  lista: str = "reduzida",
                  max_attempts: int = MAX_TENTATIVAS) -> list[tuple[str, int, int]]:
    """Joga uma partida. Devolve (palpite, código do feedback, nº de candidatas antes)."""
    ctx = _contexto(respostas, aceitas, lista)
    if answer not in ctx.respostas:
        raise RuntimeError(f"'{answer}' não está na lista de respostas.")
    alvo = ctx.respostas.index(answer)
    candidatas = np.arange(len(ctx.respostas), dtype=np.int32)
    jogadas: list[tuple[str, int, int]] = []

    for tentativa in range(1, max_attempts + 1):
        g = resolver_garantido(ctx, candidatas, max_attempts - tentativa + 1)
        if g is None:
            raise RuntimeError(f"Sem estratégia garantida em {max_attempts} tentativas.")
        fb = int(ctx.matriz[g, alvo])
        jogadas.append((ctx.palpites[g], fb, len(candidatas)))
        if g == alvo:
            return jogadas
        candidatas = candidatas[ctx.matriz[g, candidatas] == fb]
    raise RuntimeError("Passou do limite de tentativas.")


# ======================================================================
# 5) Interface
# ======================================================================
def percentil(valores_ordenados, p):
    k = max(0, math.ceil(p / 100 * len(valores_ordenados)) - 1)
    return valores_ordenados[k]


def perguntar(titulo, opcoes, padrao=None, rotulos=None):
    print(f"\n{titulo}:")
    for i, o in enumerate(opcoes, 1):
        rotulo = rotulos[o] if rotulos else o
        marca = "  (padrão)" if o == padrao else ""
        print(f"  {i}) {rotulo}{marca}")
    while True:
        try:
            entrada = input("Escolha: ").strip()
        except EOFError:
            sys.exit("\nEntrada encerrada.")
        if not entrada and padrao:
            return padrao
        if entrada.isdigit() and 1 <= int(entrada) <= len(opcoes):
            return opcoes[int(entrada) - 1]
        if entrada in opcoes:
            return entrada
        print("Opção inválida.")


def rodar_todas(respostas, aceitas, alvos, lista):
    resultados = []
    inicio = time.time()
    for i, resposta in enumerate(alvos, 1):
        try:
            jogadas = jogar_partida(respostas, aceitas, resposta, lista)
            resultados.append({
                "answer": resposta, "attempts": len(jogadas), "solved": True,
                "palpites": [j[0] for j in jogadas],
                "candidatas": [j[2] for j in jogadas],
            })
        except RuntimeError:
            resultados.append({"answer": resposta, "attempts": -1, "solved": False,
                               "palpites": None, "candidatas": None})
        if i % 500 == 0:
            print(f"  {i}/{len(alvos)} ({time.time() - inicio:.0f}s)")
    return resultados, time.time() - inicio


def mostrar_estatisticas(resultados, respostas, detalhada, tempo):
    total = len(resultados)
    resolvidas = [r for r in resultados if r["solved"]]
    tent = sorted(r["attempts"] for r in resolvidas)
    if not tent:
        print("Nenhuma palavra resolvida.")
        return

    print("\n" + "=" * 56)
    print("ESTATÍSTICAS")
    print("=" * 56)
    print(f"Palavras testadas:      {total}")
    print(f"Resolvidas:             {len(resolvidas)}")
    print(f"Não resolvidas:         {total - len(resolvidas)}")
    print(f"Média de tentativas:    {statistics.mean(tent):.3f}")
    print(f"Máximo:                 {max(tent)}")
    print(f"Acima de {MAX_TENTATIVAS} tentativas:  {sum(t > MAX_TENTATIVAS for t in tent)}")

    if not detalhada:
        print("=" * 56)
        return

    print(f"Mínimo:                 {min(tent)}")
    print(f"Mediana:                {statistics.median(tent)}")
    if len(tent) > 1:
        print(f"Desvio padrão:          {statistics.stdev(tent):.3f}")
    print(f"Percentil 90 / 99:      {percentil(tent, 90)} / {percentil(tent, 99)}")
    print(f"Tempo total:            {tempo:.1f} s ({1000 * tempo / total:.1f} ms por palavra)")

    print("\nDistribuição de tentativas:")
    contagem = Counter(tent)
    acumulado = 0
    for n in range(1, max(tent) + 1):
        q = contagem.get(n, 0)
        acumulado += q
        barra = "█" * round(40 * q / len(tent))
        print(f"  {n} tentativa(s): {q:6d}  {100 * q / len(tent):5.1f}%  "
              f"(acum. {100 * acumulado / len(tent):5.1f}%)  {barra}")

    mais_dificeis = sorted(resolvidas, key=lambda r: (-r["attempts"], r["answer"]))[:15]
    print("\n15 palavras mais difíceis (mais tentativas):")
    print("  " + ", ".join(f"{r['answer']}({r['attempts']})" for r in mais_dificeis))

    com_caminho = [r for r in resolvidas if r["palpites"]]
    if com_caminho:
        conjunto_respostas = set(respostas)
        todos = [p for r in com_caminho for p in r["palpites"]]
        aberturas = Counter(r["palpites"][0] for r in com_caminho)
        fora = sum(p not in conjunto_respostas for p in todos)
        usados = Counter(todos)
        restantes = [r["candidatas"][1] if len(r["candidatas"]) > 1 else 1
                     for r in com_caminho]

        print("\nSobre os palpites jogados:")
        print(f"  Palpite de abertura:                 {aberturas.most_common(1)[0][0]}")
        print(f"  Palpites diferentes usados:          {len(usados)}")
        print(f"  Palpites fora da lista de respostas: {100 * fora / len(todos):.1f}%")
        print(f"  Candidatas restantes após o 1º palpite: "
              f"média {statistics.mean(restantes):.1f}, pior caso {max(restantes)}")
        print("  Palpites mais usados: " +
              ", ".join(f"{p}({q})" for p, q in usados.most_common(10)))
    print("=" * 56)


def salvar_csv(nome, resultados):
    caminho = DATASET / f"resultados_{nome}.csv"
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(("answer", "algorithm", "word_function", "attempts", "solved"))
        for r in resultados:
            w.writerow((r["answer"], nome, "none", r["attempts"], r["solved"]))
    print(f"Resultados por palavra salvos em: {caminho}")


def jogar_uma_palavra(respostas, aceitas, palavra, lista):
    palavra = palavra.strip().lower()
    if palavra not in set(respostas):
        sys.exit(f"'{palavra}' não está na lista de respostas escolhida.")
    jogadas = jogar_partida(respostas, aceitas, palavra, lista)
    conjunto = set(respostas)
    print(f"\nResposta secreta: {palavra}\n")
    for i, (palpite, fb, antes) in enumerate(jogadas, 1):
        nota = "" if palpite in conjunto else "  (palpite que não é resposta possível)"
        print(f"Tentativa {i}: {palpite}  {codigo_para_cores(fb)}   "
              f"candidatas antes do palpite: {antes}{nota}")
    print(f"\nResolvida em {len(jogadas)} tentativa(s).")


def main():
    ap = argparse.ArgumentParser(description="Termo com Grafos: busca AND-OR (máximo 6 tentativas)")
    ap.add_argument("--lista", choices=["total", "reduzida"])
    ap.add_argument("--modo", choices=["todas", "amostra", "palavra"])
    ap.add_argument("--amostra", type=int)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--palavra")
    ap.add_argument("--estatisticas", choices=["basicas", "detalhadas"])
    args = ap.parse_args()

    print("=== Termo com Grafos: busca AND-OR ===")
    aceitas = ler_lista(ARQ_ACEITAS)
    solucoes = ler_lista(ARQ_RESPOSTAS) if ARQ_RESPOSTAS.exists() else None

    lista = args.lista or perguntar(
        "Qual lista usar", ["total", "reduzida"],
        padrao="reduzida" if solucoes else "total",
        rotulos={"total": f"Total: as {len(aceitas)} palavras aceitas (respostas e palpites)",
                 "reduzida": f"Reduzida: soluções possíveis ({len(solucoes) if solucoes else 'arquivo não encontrado'}) como respostas"})

    if lista == "reduzida" and solucoes is None:
        sys.exit(f"Arquivo não encontrado: {ARQ_RESPOSTAS}")
    respostas = aceitas if lista == "total" else solucoes
    print(f"\nLista {lista}: {len(respostas)} respostas | {len(aceitas)} palavras aceitas como palpite")

    modo = args.modo or perguntar(
        "O que fazer", ["todas", "amostra", "palavra"],
        rotulos={"todas": "Simular TODAS as respostas",
                 "amostra": "Simular uma amostra aleatória",
                 "palavra": "Jogar uma palavra passo a passo"})

    if modo == "palavra":
        palavra = args.palavra or input("\nPalavra (resposta secreta): ")
        jogar_uma_palavra(respostas, aceitas, palavra, lista)
        return

    alvos = list(respostas)
    if modo == "amostra":
        n = args.amostra or int(input("\nTamanho da amostra [200]: ").strip() or 200)
        alvos = sorted(random.Random(args.seed).sample(alvos, min(n, len(alvos))))
        print(f"Amostra de {len(alvos)} palavras (semente {args.seed}).")

    nivel = args.estatisticas or perguntar(
        "Estatísticas", ["basicas", "detalhadas"], padrao="basicas",
        rotulos={"basicas": "Básicas", "detalhadas": "Detalhadas (mais números)"})

    print(f"\nExecutando a busca AND-OR com lista {lista}...")
    resultados, tempo = rodar_todas(respostas, aceitas, alvos, lista)
    mostrar_estatisticas(resultados, respostas, nivel == "detalhadas", tempo)
    salvar_csv(f"busca_and_or_{lista}", resultados)


if __name__ == "__main__":
    main()