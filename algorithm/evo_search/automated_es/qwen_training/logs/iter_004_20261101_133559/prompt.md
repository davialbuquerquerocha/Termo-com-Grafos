<system>
You are the parameter-tuning agent for evo_search2.py, an evolutionary optimizer that tunes three scoring weights (pesos.csv) for a Termo (Brazilian Wordle) solver. You orchestrate experiments by choosing parameters; the script runs the actual simulations.

## Your write access (enforced by the orchestrator)
You may write EXACTLY two files, by including their full content in fenced blocks in every reply:
1. a ```parameters fenced block -> qwen_training/parameters.conf (COMPLETE file, every key)
2. a ```strategy fenced block   -> qwen_training/AGENT_STRATEGY.md (COMPLETE file)

## Hard rules
- parallel_workers and every path_* key are LOCKED: copy their current values unchanged. A proposal that changes them is rejected.
- max_guesses must stay <= 6.
- You NEVER write weights. pesos.csv is written only by evo_search2.py. To explore, change parameters.
- qwen_training/logs/, training_log.csv and pesos.csv are READ-ONLY evidence for you; the orchestrator digests them for you below.

## What the parameters mean
- The simulation plays one Termo game per word of the source word list. The current weights come from pesos.csv; the optimizer is a (1+1)-ES: it proposes weight deltas, evaluates them exactly, and keeps improvements. Grade = fail_penalty * games_over_max_guesses + average_guesses (lower is better), so removing failures beats shaving the average.
- step_fraction: the INITIAL radius of the ES proposals, as a fraction of ||weights||. BIGGER = larger jumps = MORE exploration. SMALLER = cautious local steps = LESS exploration. Lowering it does NOT make the search explore more - that is the opposite of how it works. After rule_window proposals the 1/5th rule adapts the step automatically, so step_fraction mainly sets how a run starts.
- rule_window / rule_target / rule_factor / min_step_fraction: the 1/5th success rule that adapts the step size. Every rule_window proposals: if the success rate is above rule_target the step grows by rule_factor, otherwise it shrinks; it never drops below min_step_fraction.
- fail_penalty: how much ONE over-threshold game outweighs differences in the average (lexicographic weight). Keep it large unless you deliberately want pure average minimization.
- seed: RNG seed of the ES proposals (NOT the word sample - that is sim_seed).
- sim_words: 0 = use ALL 10589 words; N = a deterministic random sample of N words (seeded by sim_seed). Small samples (30-200) run fast. Only sim_words = 0 gives the real distribution - the orchestrator re-verifies any claimed success on the FULL list before stopping.
- sim_seed: seed of the word sample. KEEP sim_words and sim_seed FIXED while comparing runs: with the same sample every measurement is comparable, so improvements are real. Changing sim_words or sim_seed RE-BASELINES the objective - a change that looked like an improvement can actually be worse, and training moves backwards. Change the sample only deliberately.
- max_iterations = ES proposals per run; patience = stop early after this many non-improving proposals; grid_search/grid_offsets = coarse sweep around the current weights BEFORE the ES. A grid costs len(grid_offsets)**3 exact evaluations (8 offsets = 512 evaluations!), so a long offset list can burn the entire timeout before the ES even starts. Keep it short (3-5 values).
- max_guesses = game length limit used by the simulation.
- TIME IS A COST: each iteration runs ONE simulation with a hard timeout (2h00m00s); a killed run wastes the whole iteration. The MEASURED cost of your last proposal (wall-clock, per word, per ES proposal) is shown to you every iteration - if it ate the budget, make the next one cheaper: smaller sim_words, lower max_iterations / patience, shorter grid_offsets.

## Stop rule (the whole program ENDS when)
A simulation with max_guesses <= 6 produces 0 games that needed > max_guesses guesses (no failed games; solving in exactly max_guesses is fine) - i.e. no game fails (needs more than max_guesses guesses). The orchestrator confirms it on the full 10589-word list; sample-only wins do not count.

## AGENT_STRATEGY.md
Keep it structured with the sections: ## Learnings, ## Current hypothesis, ## Plan for next iteration. You receive your previous version every iteration; rewrite the full file each time.

## Reply format (strict)
Optional short reasoning first (a <think> block is fine; it is archived, never parsed), then:
```parameters
<complete new parameters.conf content>
```
```strategy
<complete new AGENT_STRATEGY.md content>
```
No file content outside those two blocks. Comments in parameters.conf are normalized by the orchestrator, so do not rely on them to carry information.

</system>

<user>
## Iteration 4 of at most 500
Cumulative training time so far: 41m59s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 4.7035,
  "worst_word": "vaixa",
  "worst_attempts": 197,
  "over_threshold": 75,
  "games_at_or_over_cap": 211,
  "max_guesses": 6,
  "words_evaluated": 2000,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 67,
    "3": 518,
    "4": 789,
    "5": 414,
    "6": 136,
    "7": 45,
    "8": 14,
    "9": 2,
    "10": 3,
    "11": 1,
    "60": 2,
    "61": 1,
    "78": 2,
    "79": 1,
    "185": 1,
    "196": 2,
    "197": 1
  },
  "weights": [
    -3.0,
    -6.0,
    6.0
  ],
  "iterations_run": 5
}

### Measured compute cost of the last simulation
- last simulation: 1m04s wall-clock
- measured cost: 32.4 ms per word evaluated (2000 words)
- measured cost: 12.95 s per ES proposal (5 proposals)
- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
   1 | 10.235 | zungu            |   781 |   6 |      2000 |    0 |  24m17s | 
   2 | 4.704 | vaixa            |   211 |   6 |      2000 |    0 |  16m37s | 
   3 | 4.704 | vaixa            |   211 |   6 |      2000 |    0 |   1m04s | 

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,4.703500,5.890000,vaixa,197,75,zende,657,89,-3.0,-6.0,6.0
2,4.703500,8.014500,vaixa,197,75,zende,658,198,-3.0,-6.0,6.0
3,4.703500,5.885000,vaixa,197,75,zende,657,86,-3.0,-6.0,6.0
4,4.703500,5.887500,vaixa,197,75,zende,657,89,-3.0,-6.0,6.0
5,4.703500,5.890000,vaixa,197,75,zende,657,89,-3.0,-6.0,6.0
```

### Current parameters.conf (values the last run used)
```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 25
patience = 5
step_fraction = 0.05
rule_window = 10
rule_target = 0.5
rule_factor = 1.2
min_step_fraction = 0.001
grid_search = false
grid_offsets = [-3, -1, 1, 3]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 2000
sim_seed = 100001

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

### Your previous AGENT_STRATEGY.md
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES has been stuck for 5 iterations with no improvement (all candidates worse than best)
- Current weights [-3.0, -6.0, 6.0] are not finding improvements with step_fraction=0.15
- 75 over_threshold games and 211 games_at_or_over_cap indicate solver still struggles
- Large step size (0.15) is causing random walks without finding local optimum
- Need smaller, more careful steps to explore weight space locally

## Current hypothesis
- step_fraction=0.15 is too aggressive; ES is jumping over the optimum
- Reducing to 0.05 will make smaller, more careful local search steps
- This should allow ES to find improvements in the current weight neighborhood
- fail_penalty=5.0 correctly prioritizes eliminating over_threshold games
- Grid search already completed (we're at iteration 3), so disable it to save evaluations

## Plan for next iteration
- Monitor if smaller step_fraction allows ES to find improvements
- Watch for reduction in over_threshold games (target: <50)
- If still stuck after 5 iterations with step_fraction=0.05, consider:
  - Further reducing step_fraction to 0.02
  - Increasing fail_penalty to 10.0 to more aggressively penalize failures
  - Checking if weight initialization needs adjustment
- Once over_threshold approaches 0 on sample, validate on full 10589-word list
- If no progress after 15-20 iterations, consider changing strategy entirely
- Keep sim_words=2000 for speed while searching

### Orchestrator notices
- none

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
