import argparse
import csv
import itertools
import multiprocessing
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple
import numpy as np

# Parameters
MAX_ITERATIONS = 2000                  # hard stop
PATIENCE = 200                         # stop after this many non-improving proposals
STEP_FRACTION = 1                      # INITIAL proposal radius as a fraction of ||weights|| (then adapted)
RULE_WINDOW = 20                       # 1/5th rule: proposals per adaptation check
RULE_TARGET = 0.2                      # 1/5th rule: target success rate
RULE_FACTOR = 1.5                      # 1/5th rule: grow/shrink multiplier when off target
MIN_STEP_FRACTION = 0.001              # 1/5th rule: never let the step collapse to zero
GRID_SEARCH = True                     # True: sweep a coarse grid first, then refine with ES
GRID_OFFSETS = (-4, -1, 1, 4)          # grid = current weights + these offsets (per weight)
SEED = 7                               # seed for rng
MAX_GUESSES = 6                        # Termo standard; games needing MORE guesses than this are counted
FAIL_PENALTY = 2                       # lexicographic weight: one over-threshold game outweighs any average difference
PARALLEL_WORKERS = 17                  # games evaluated in parallel (physical CPU cores; set 1 for serial)

# Directories
MODULE_DIR =          Path(__file__).resolve().parent
DATASET_DIR =         MODULE_DIR.parents[2] / "dataset"

WEIGHTS_PATH =        MODULE_DIR / "pesos.csv"
LETTERS_PATH =        DATASET_DIR / "statistics" / "letters_position.csv"
DEFAULT_ACCEPTED_WORDS_PATH = DATASET_DIR / "words" / "palavras_aceitas500.txt"
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "accepted_words_path",
        nargs="?",
        type=Path,
        default=DEFAULT_ACCEPTED_WORDS_PATH,
        help="path to the accepted-words input file",
    )
    ACCEPTED_WORDS_PATH = parser.parse_args().accepted_words_path
else:
    ACCEPTED_WORDS_PATH = DEFAULT_ACCEPTED_WORDS_PATH
TRAIN_LOG_PATH =      MODULE_DIR / "training_log.csv"

with WEIGHTS_PATH.open(encoding="utf-8") as weights_file:
    weight_rows = list(csv.reader(weights_file))

if len(weight_rows) != 1 or len(weight_rows[0]) != 3:
    raise ValueError("pesos.csv must contain one line with exactly three numbers")

WEIGHTS = np.array([float(value) for value in weight_rows[0]], dtype=float)

with LETTERS_PATH.open(encoding="utf-8") as letters_file:
    LETTERS = [
        (row[0], row[1])
        for row in (line.strip().split(",") for line in letters_file)
        if len(row) >= 2
    ]

with ACCEPTED_WORDS_PATH.open(encoding="utf-8") as words_file:
    ACCEPTED_WORDS = [line.strip() for line in words_file]

def build_wordle_stats(words: list[str]) -> list[tuple[np.ndarray, str, int]]:
    """Same counts as the original triple loop (verified identical output),
    vectorized so the LIVE per-turn rebuild inside algorithm() stays cheap:
    counts[2] = words with the letter at this position,
    counts[1] = words with the letter somewhere else,
    counts[0] = words without the letter."""
    normalized_words = [word.strip().lower() for word in words if word.strip()]
    if not normalized_words:
        return []
    letters = sorted({letter for word in normalized_words for letter in word})
    max_position = max((len(word) for word in normalized_words), default=0)
    codes = np.array(
        [[ord(ch) for ch in word.ljust(max_position, "\0")] for word in normalized_words]
    )
    in_word = {letter: (codes == ord(letter)).any(axis=1) for letter in letters}
    stats = []

    for position in range(1, max_position + 1):
        column = codes[:, position - 1]
        for letter in letters:
            at_position = column == ord(letter)
            present = in_word[letter]
            counts = np.array(
                [
                    int((~present).sum()),
                    int((present & ~at_position).sum()),
                    int(at_position.sum()),
                ]
            )
            stats.append((counts, letter, position))

    return stats

WORDLE_STATS = build_wordle_stats(ACCEPTED_WORDS)

def rank_letters(
    wordle_stats: list[tuple[np.ndarray, str, int]],
    weights: np.ndarray,
) -> list[tuple[float, str, int]]:
    return [
        (float(counts @ weights), letter, position)
        for counts, letter, position in wordle_stats
    ]

def rank_words(
    words: list[str],
    letter_ranks: list[tuple[float, str, int]],
) -> list[tuple[str, float]]:
    scores_by_letter_position = {
        (letter, position): score
        for score, letter, position in letter_ranks
    }
    return [
        (
            word,
            sum(
                scores_by_letter_position.get((letter, position), 0.0)
                for position, letter in enumerate(word.lower(), start=1)
            ),
        )
        for word in words
    ]

BLACK = 0
YELLOW = 1
GREEN = 2
Feedback = tuple[int, ...]

guessable_words = ACCEPTED_WORDS.copy()


def wordle_try(answer: str, guess: str) -> Feedback:
    """Return one color code per guessed position: black=0, yellow=1, green=2."""
    answer = answer.strip().lower()
    guess = guess.strip().lower()
    if len(answer) != len(guess):
        raise ValueError("answer and guess must have the same length")

    feedback = [BLACK] * len(guess)
    remaining = Counter()

    for position, (answer_letter, guess_letter) in enumerate(zip(answer, guess)):
        if answer_letter == guess_letter:
            feedback[position] = GREEN
        else:
            remaining[answer_letter] += 1

    for position, guess_letter in enumerate(guess):
        if feedback[position] == GREEN:
            continue
        if remaining[guess_letter] > 0:
            feedback[position] = YELLOW
            remaining[guess_letter] -= 1

    return tuple(feedback)


# Accumulated knowledge for the exploration rules in algorithm(). It is
# rebuilt from scratch at the start of every game (the first call always
# arrives with previous_guess=None) and extended after every feedback, so it
# always describes THIS game only.
_GREEN: dict[int, str] = {}              # position -> letter confirmed green there
_YELLOW_TRIED: dict[str, set[int]] = {}  # letter -> positions it already occupied as yellow
_BLACK_SEEN: set[str] = set()            # letters that came back black at least once
_PRESENT: set[str] = set()               # letters confirmed somewhere in the answer


def _reset_knowledge() -> None:
    """Forget everything: a new game is starting."""
    _GREEN.clear()
    _YELLOW_TRIED.clear()
    _BLACK_SEEN.clear()
    _PRESENT.clear()


def _update_knowledge(guess: str, feedback: tuple[int, ...]) -> None:
    """Record what the latest feedback settled about letters and positions."""
    for position, (letter, code) in enumerate(zip(guess, feedback)):
        if code == GREEN:
            _GREEN[position] = letter
            _PRESENT.add(letter)
        elif code == YELLOW:
            _YELLOW_TRIED.setdefault(letter, set()).add(position)
            _PRESENT.add(letter)
        else:
            _BLACK_SEEN.add(letter)


def _exploration_pool(guessable_words: list[str]) -> list[str]:
    """Slice of the unused vocabulary that still gathers information.

    A word qualifies only if it never places a confirmed green letter back in
    its own position (that result is already known, so re-testing it teaches
    nothing) and every letter known to be in the answer but not yet placed
    (yellow) sits in a position it has never occupied before - and never in a
    position already confirmed for another letter. Letters that only ever
    came back black are provably absent and are avoided whenever possible.
    When no word can satisfy everything at once, the constraints are relaxed
    one step at a time so a legal guess is always available.
    """
    unplaced = [
        (letter, spots)
        for letter, spots in _YELLOW_TRIED.items()
        if letter not in _GREEN.values()
    ]
    strict: list[str] = []      # every yellow placed, none on a dead spot
    moved: list[str] = []       # every yellow placed in at least one fresh spot
    green_free: list[str] = []  # only the green rule holds
    for word in guessable_words:
        if any(word[position] == letter for position, letter in _GREEN.items()):
            continue  # would re-test a green letter where it is already known
        green_free.append(word)
        is_strict = True
        is_moved = True
        for letter, spots in unplaced:
            fresh = [
                position
                for position, word_letter in enumerate(word)
                if word_letter == letter
                and position not in spots
                and position not in _GREEN
            ]
            if not fresh:
                is_strict = False
                is_moved = False
                break
            if len(fresh) < word.count(letter):
                is_strict = False  # an extra occurrence lands on a dead spot
        if is_strict:
            strict.append(word)
        elif is_moved:
            moved.append(word)
    for pool in (strict, moved, green_free):
        if pool:
            break
    else:
        pool = list(guessable_words)
    # Black rule: a letter that only ever came back black is provably absent,
    # so any slot it occupies is a wasted test. Prefer words without one when
    # the current tier can still supply them.
    absent = _BLACK_SEEN - _PRESENT
    if absent:
        clean = [word for word in pool if not any(letter in word for letter in absent)]
        if clean:
            pool = clean
    return pool


def algorithm(
    guessable_words: list[str],
    accepted_words: list[str],
    wordle_stats: list[tuple[np.ndarray, str, int]],
    weights: np.ndarray,
    previous_guess: str | None = None,
    feedback: tuple[int, ...] | None = None,
) -> str:
    """Filter answer candidates from feedback, then pick the next guess.

    With MORE than two candidates the selection pool is the full unused
    guessable vocabulary filtered by _exploration_pool(): the guess never
    repeats a confirmed green letter in its position and necessarily moves
    every known yellow letter to a position it has not occupied yet, so every
    probe gathers new information instead of re-testing known facts.

    The letter statistics are recomputed on the LIVE candidate list every
    turn, not on the frozen global table: a letter that every surviving
    candidate shares (or none has) carries no useful information any more,
    and the scorer must see that to stop wasting slots on it.

    HARD RULE: with two or fewer candidates left, exploring can no longer pay
    off, so the guess is always one of the candidates - it wins immediately
    with probability >= 1/2 and always finishes within two guesses.
    """
    guessable_words[:] = [word.strip().lower() for word in guessable_words if word.strip()]
    accepted_words[:] = [word.strip().lower() for word in accepted_words if word.strip()]

    if (previous_guess is None) != (feedback is None):
        raise ValueError("previous_guess and feedback must be provided together")
    if previous_guess is None:
        _reset_knowledge()  # first call of a new game
    else:
        accepted_words[:] = [
            candidate
            for candidate in accepted_words
            if wordle_try(candidate, previous_guess) == feedback
        ]
        if not accepted_words:
            raise RuntimeError("Feedback eliminated every possible answer")
        _update_knowledge(previous_guess, feedback)

    if not guessable_words:
        raise RuntimeError("No unused guess words remain")

    # FIX 1: no noise() here. Exploration noise belongs only in the trainer;
    # evaluating a fixed weight vector must always return the same grade.
    # FIX 3: rank with LIVE letter statistics (this game's candidates), so the
    # weights always judge letters by what they can still reveal here.
    letter_ranks = rank_letters(build_wordle_stats(accepted_words), weights)

    # HARD RULE: with <= 2 candidates, stop exploring and try to win.
    if len(accepted_words) <= 2:
        ranked_words = rank_words(accepted_words, letter_ranks)
    else:
        # Otherwise rank the information-gathering slice of the full unused
        # vocabulary: greens stay out of their spots, yellows change spots.
        ranked_words = rank_words(_exploration_pool(guessable_words), letter_ranks)

    guess, _score = max(ranked_words, key=lambda item: item[1])

    if guess in guessable_words:
        guessable_words.remove(guess)
    return guess


def wordle_game(
    answer: str,
    algorithm: Callable[..., str],
    accepted_words: list[str],
    wordle_stats: list[tuple[np.ndarray, str, int]],
    weights: np.ndarray,
    guessable_words: list[str] | None = None,
) -> int:
    answer = answer.strip().lower()
    possible_answers = [word.strip().lower() for word in accepted_words if word.strip()]
    if answer not in possible_answers:
        raise ValueError(f"Answer {answer!r} is not in the possible-answer list")

    guess_pool = ACCEPTED_WORDS if guessable_words is None else guessable_words
    available_guesses = [word.strip().lower() for word in guess_pool if word.strip()]
    if answer not in available_guesses:
        raise ValueError(f"Answer {answer!r} is not in the legal-guess list")

    previous_guess = None
    previous_feedback = None
    attempts = 0

    while available_guesses:
        guess = algorithm(
            available_guesses,
            possible_answers,
            wordle_stats,
            weights,
            previous_guess,
            previous_feedback,
        )
        attempts += 1
        if guess == answer:
            return attempts

        previous_feedback = wordle_try(answer, guess)
        previous_guess = guess

    raise RuntimeError("The answer was not found before guesses were exhausted")


class GameStats(NamedTuple):
    """Aggregate result of evaluating one weight vector over every word."""

    average: float
    worst_word: str
    worst_attempts: int
    over_threshold: int  # games that needed MORE than MAX_GUESSES guesses


def grade_of(stats: GameStats) -> float:
    """Lexicographic fitness: fewer over-threshold games FIRST, then lower average.

    FAIL_PENALTY is far larger than any achievable difference between averages,
    so removing a single over-threshold game always wins; the average only
    breaks ties between weight vectors with the same number of over-threshold
    games. Set FAIL_PENALTY = 0 to go back to pure average minimization.
    """
    return stats.over_threshold * FAIL_PENALTY + stats.average


_EXECUTOR: ProcessPoolExecutor | None = None


def _worker_play_game(task: tuple[str, np.ndarray]) -> int:
    """Run inside a worker process: play one full game for (answer, weights).th three implementa

    ACCEPTED_WORDS and WORDLE_STATS are module globals, so every worker already
    has them (inherited via fork on Linux, rebuilt on import via spawn on
    Windows). wordle_game() rebuilds its own working lists on every call, so
    tasks never share mutable state and results are identical to serial runs.
    The parallel path evaluates against the module-level word lists, which is
    what every call site in this script passes anyway.
    """
    answer, weights = task
    return wordle_game(
        answer,
        algorithm,
        ACCEPTED_WORDS,
        WORDLE_STATS,
        weights,
        ACCEPTED_WORDS.copy(),
    )


def _get_executor() -> ProcessPoolExecutor:
    """Create the worker pool once and reuse it for every evaluation."""
    global _EXECUTOR
    if _EXECUTOR is None:
        context = (
            multiprocessing.get_context("fork")
            if "fork" in multiprocessing.get_all_start_methods()
            else None  # Windows: fall back to the default spawn method
        )
        _EXECUTOR = ProcessPoolExecutor(
            max_workers=PARALLEL_WORKERS,
            mp_context=context,
        )
    return _EXECUTOR


def classify_algorithm(
    algorithm: Callable[..., str],
    accepted_words: list[str],
    wordle_stats: list[tuple[np.ndarray, str, int]],
    weights: np.ndarray,
) -> GameStats:
    """Play every word once; report average, worst case and over-threshold count.

    Games are independent and deterministic, so with PARALLEL_WORKERS > 1 they
    are distributed across worker processes and gathered in word order - the
    returned stats are exactly the same as the serial version.
    """
    total = len(accepted_words)
    if total == 0:
        raise ValueError("accepted_words must not be empty")

    if PARALLEL_WORKERS > 1:
        tasks = [(word, weights) for word in accepted_words]
        chunksize = max(1, total // (PARALLEL_WORKERS * 16))
        attempts_list = list(
            _get_executor().map(_worker_play_game, tasks, chunksize=chunksize)
        )
    else:
        attempts_list = [
            wordle_game(
                word,
                algorithm,
                accepted_words,
                wordle_stats,
                weights,
                ACCEPTED_WORDS.copy(),
            )
            for word in accepted_words
        ]

    counter = 0
    worst_word = ""
    worst_attempts = 0
    over_threshold = 0
    for word, attempts in zip(accepted_words, attempts_list):
        counter += attempts
        if attempts > worst_attempts:
            worst_attempts, worst_word = attempts, word
        if attempts > MAX_GUESSES:
            over_threshold += 1

    return GameStats(counter / total, worst_word, worst_attempts, over_threshold)

def propose(weights: np.ndarray, step_fraction: float, rng: np.random.Generator) -> np.ndarray:
    """Small random step around the current best weights."""
    direction = rng.normal(size=weights.shape)
    direction /= np.linalg.norm(direction)
    return weights + direction * step_fraction * np.linalg.norm(weights)


def save_weights(weights: np.ndarray) -> None:
    with WEIGHTS_PATH.open(mode="w", newline="", encoding="utf-8") as weights_file:
        csv.writer(weights_file).writerow(np.asarray(weights, dtype=float).tolist())


def run_es(
    best_weights: np.ndarray,
    best_stats: GameStats,
    rng: np.random.Generator,
) -> tuple[np.ndarray, GameStats]:
    """(1+1) evolution strategy: propose, evaluate exactly, keep only if
    better according to grade_of (over-threshold games first, then average).
    The proposal step size adapts itself by the 1/5th success rule."""
    stale = 0
    step_fraction = STEP_FRACTION
    window: list[int] = []  # recent proposals: 1 = improved, 0 = rejected
    with TRAIN_LOG_PATH.open("w", newline="", encoding="utf-8") as log_file:
        writer = csv.writer(log_file)
        writer.writerow(
            [
                "iteration",
                "best_grade",
                "candidate_grade",
                "best_worst_word",
                "best_worst_attempts",
                "best_over_threshold",
                "candidate_worst_word",
                "candidate_worst_attempts",
                "candidate_over_threshold",
                "w0",
                "w1",
                "w2",
            ]
        )
        for iteration in range(1, MAX_ITERATIONS + 1):
            candidate = propose(best_weights, step_fraction, rng)
            candidate_stats = classify_algorithm(
                algorithm, ACCEPTED_WORDS, WORDLE_STATS, candidate
            )
            improved = grade_of(candidate_stats) < grade_of(best_stats)
            if improved:
                best_weights, best_stats = candidate, candidate_stats
                stale = 0
                save_weights(best_weights)  # only ever commit improvements
            else:
                stale += 1
            # 1/5th success rule: too many successes means steps are too
            # small, too few means they are too big. Grown/shrunk every
            # RULE_WINDOW proposals so one lucky/unlucky event cannot
            # distort the step size.
            window.append(1 if improved else 0)
            if len(window) >= RULE_WINDOW:
                if sum(window) / len(window) > RULE_TARGET:
                    step_fraction *= RULE_FACTOR
                else:
                    step_fraction /= RULE_FACTOR
                step_fraction = max(step_fraction, MIN_STEP_FRACTION)
                window.clear()
            writer.writerow(
                [
                    iteration,
                    f"{best_stats.average:.6f}",
                    f"{candidate_stats.average:.6f}",
                    best_stats.worst_word,
                    best_stats.worst_attempts,
                    best_stats.over_threshold,
                    candidate_stats.worst_word,
                    candidate_stats.worst_attempts,
                    candidate_stats.over_threshold,
                    *best_weights,
                ]
            )
            if iteration % 10 == 0 or improved:
                print(
                    f"iter {iteration:3d}  best={best_stats.average:.4f}  "
                    f"last={candidate_stats.average:.4f}  "
                    f"worst={best_stats.worst_word}({best_stats.worst_attempts})  "
                    f">{MAX_GUESSES} guesses: {best_stats.over_threshold}  "
                    f"w={np.round(best_weights, 4).tolist()}"
                )
            if stale >= PATIENCE:
                print(f"no improvement in {PATIENCE} proposals - stopping")
                break
    return best_weights, best_stats


def run_grid_search() -> tuple[np.ndarray, GameStats]:
    """Coarse sweep CENTERED on the current weights: every candidate is
    pesos.csv plus one offset combination. Because the sweep follows wherever
    the weights start, the same grid works smoothly from 100 to 10000 words."""
    center = WEIGHTS.copy()
    best_weights = center.copy()
    best_stats = classify_algorithm(algorithm, ACCEPTED_WORDS, WORDLE_STATS, best_weights)
    for offsets in itertools.product(GRID_OFFSETS, repeat=len(center)):
        candidate = center + np.array(offsets)
        stats = classify_algorithm(algorithm, ACCEPTED_WORDS, WORDLE_STATS, candidate)
        if grade_of(stats) < grade_of(best_stats):
            best_weights, best_stats = candidate, stats
    print(
        f"grid best: {best_stats.average:.4f} with weights {best_weights.tolist()}  "
        f"worst={best_stats.worst_word}({best_stats.worst_attempts})  "
        f">{MAX_GUESSES} guesses: {best_stats.over_threshold}"
    )
    return best_weights, best_stats


def train(algorithm_fn, accepted_words, wordle_stats, weights: np.ndarray) -> np.ndarray:
    """Kept for compatibility with the old call signature; runs the new loop."""
    rng = np.random.default_rng(SEED)
    best_weights = np.asarray(weights, dtype=float).copy()
    best_stats = classify_algorithm(algorithm_fn, accepted_words, wordle_stats, best_weights)
    print(
        f"start: average guesses = {best_stats.average:.4f}  "
        f"worst={best_stats.worst_word}({best_stats.worst_attempts})  "
        f">{MAX_GUESSES} guesses: {best_stats.over_threshold}"
    )
    if GRID_SEARCH:
        best_weights, best_stats = run_grid_search()
        save_weights(best_weights)
    best_weights, best_stats = run_es(best_weights, best_stats, rng)
    save_weights(best_weights)
    if _EXECUTOR is not None:
        _EXECUTOR.shutdown(wait=True)  # release worker processes
    print(
        f"saved best weights {np.round(best_weights, 4).tolist()} "
        f"(average guesses {best_stats.average:.4f})  "
        f"worst={best_stats.worst_word}({best_stats.worst_attempts})  "
        f">{MAX_GUESSES} guesses: {best_stats.over_threshold}"
    )
    return best_weights


if __name__ == "__main__":
    train(algorithm, ACCEPTED_WORDS, WORDLE_STATS, WEIGHTS)
