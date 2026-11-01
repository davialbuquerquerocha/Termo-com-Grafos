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
## Iteration 15 of at most 500
Cumulative training time so far: 48m51s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 3.238,
  "worst_word": "ilhas",
  "worst_attempts": 6,
  "over_threshold": 0,
  "games_at_or_over_cap": 1,
  "max_guesses": 6,
  "words_evaluated": 500,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 55,
    "3": 284,
    "4": 145,
    "5": 14,
    "6": 1
  },
  "weights": [
    3.043571034697342,
    0.7315287377170936,
    9.498993376063998
  ],
  "iterations_run": 5
}

### Measured compute cost of the last simulation
- last simulation: 0m44s wall-clock
- measured cost: 88.3 ms per word evaluated (500 words)
- measured cost: 8.83 s per ES proposal (5 proposals)
- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
   1 | 10.235 | zungu            |   781 |   6 |      2000 |    0 |  24m17s | 
   2 | 4.704 | vaixa            |   211 |   6 |      2000 |    0 |  16m37s | 
   3 | 4.704 | vaixa            |   211 |   6 |      2000 |    0 |   1m04s | 
   4 | 4.704 | vaixa            |   211 |   6 |      2000 |    0 |   0m46s | 
   5 | 3.266 | axilo            |     4 |   6 |       500 |    0 |   0m40s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
   6 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m39s | 
   7 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m24s | 
   8 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m24s | 
   9 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m28s | 
  10 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m30s | 
  11 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m32s | 
  12 | 3.945 | atare            |   118 |   6 |      2000 |    0 |   0m58s | 
  13 | 3.238 | ilhas            |     1 |   6 |       500 |    0 |   0m41s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  14 | 3.238 | ilhas            |     1 |   6 |       500 |    0 |   0m44s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,3.238000,4.754000,ilhas,6,0,zelar,11,83,3.043571034697342,0.7315287377170936,9.498993376063998
2,3.238000,3.900000,ilhas,6,0,gozam,7,6,3.043571034697342,0.7315287377170936,9.498993376063998
3,3.238000,3.826000,ilhas,6,0,lemas,8,11,3.043571034697342,0.7315287377170936,9.498993376063998
4,3.238000,4.706000,ilhas,6,0,agino,9,71,3.043571034697342,0.7315287377170936,9.498993376063998
5,3.238000,4.316000,ilhas,6,0,fanho,9,41,3.043571034697342,0.7315287377170936,9.498993376063998
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

max_iterations = 30
patience = 5
step_fraction = 1.0
rule_window = 5
rule_target = 0.3
rule_factor = 5.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-10, -5, 5, 10]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 500
sim_seed = 100003

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

### Your previous AGENT_STRATEGY.md
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 (8+ iterations with no improvement)
- Current weights [3.04, 0.73, 9.50] produce 1 game at/over cap on 500-word sample
- ES candidates consistently worse than current best (3.94 vs 3.24)
- step_fraction=1.0 already at maximum but still not escaping
- 1/5th rule never triggered growth due to no improvements
- Average (3.24) is very close to success but games_at_or_over_cap (1) is blocking factor
- Sample verification fails on full list - need to ensure improvements generalize

## Current hypothesis
- Local optimum trap requires more aggressive exploration to escape
- Current grid_offsets [-5,-2,2,5] are too conservative
- ES stuck refining around bad weights; need to jump to better region first
- Larger grid_offsets [-10,-5,5,10] will probe more distant regions
- Increased rule_factor (5.0) will allow faster step growth when we succeed
- Increased max_iterations (30) and patience (5) will allow more exploration per run
- Keep sim_words=500 for fast iteration cycles while close to success

## Plan for next iteration
- Enable grid_search=true with 4 larger offsets to explore coarse space first
- Keep sim_words=500 for faster iteration cycles (we're close to success)
- Keep step_fraction=1.0 for maximum exploration
- Adjust rule parameters: rule_factor=5.0 (faster growth when we succeed)
- Increase max_iterations to 30 to allow more proposals per run
- Increase patience to 5 to avoid premature termination
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If grid search finds better region, ES will continue from there
- Once games_at_or_over_cap reaches 0 on 500 words, run full 10589-word validation
- If still stuck after 30 iterations, consider:
  - Further reducing sim_words to 200 for faster cycles
  - Complete reset with different initial weights
  - Manual weight perturbation based on analysis of worst words
- Keep patience=5 to maximize iterations per run
- If ES continues to stagnate, consider complete reset with fresh weights

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
