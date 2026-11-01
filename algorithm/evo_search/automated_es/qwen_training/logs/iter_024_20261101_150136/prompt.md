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
## Iteration 24 of at most 500
Cumulative training time so far: 1h00m04s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 3.544,
  "worst_word": "miojo",
  "worst_attempts": 6,
  "over_threshold": 0,
  "games_at_or_over_cap": 2,
  "max_guesses": 6,
  "words_evaluated": 1000,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 50,
    "3": 428,
    "4": 448,
    "5": 71,
    "6": 2
  },
  "weights": [
    20.843292317311434,
    10.657776183650277,
    38.31359576024953
  ],
  "iterations_run": 5
}

### Measured compute cost of the last simulation
- last simulation: 0m29s wall-clock
- measured cost: 29.2 ms per word evaluated (1000 words)
- measured cost: 5.85 s per ES proposal (5 proposals)
- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
  10 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m30s | 
  11 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m32s | 
  12 | 3.945 | atare            |   118 |   6 |      2000 |    0 |   0m58s | 
  13 | 3.238 | ilhas            |     1 |   6 |       500 |    0 |   0m41s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  14 | 3.238 | ilhas            |     1 |   6 |       500 |    0 |   0m44s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  15 | 3.630 | acaja            |    13 |   6 |      1000 |    0 |   2m36s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  16 | 3.630 | acaja            |    13 |   6 |      1000 |    0 |   0m16s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  17 | 3.593 | acaja            |     8 |   6 |      1000 |    0 |   0m15s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  18 | 3.593 | acaja            |     8 |   6 |      1000 |    0 |   0m13s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  19 | 3.593 | acaja            |     8 |   6 |      1000 |    0 |   0m13s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  20 | 3.548 | miojo            |     2 |   6 |      1000 |    0 |   5m01s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  21 | 3.545 | miojo            |     2 |   6 |      1000 |    0 |   1m03s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  22 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   1m03s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  23 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   0m29s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,3.544000,5.221000,miojo,6,0,zinga,26,197,20.843292317311434,10.657776183650277,38.31359576024953
2,3.544000,3.581000,miojo,6,0,traze,8,5,20.843292317311434,10.657776183650277,38.31359576024953
3,3.544000,3.595000,miojo,6,0,caira,6,0,20.843292317311434,10.657776183650277,38.31359576024953
4,3.544000,4.238000,miojo,6,0,apapa,7,8,20.843292317311434,10.657776183650277,38.31359576024953
5,3.544000,4.004000,miojo,6,0,gemam,7,3,20.843292317311434,10.657776183650277,38.31359576024953
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

max_iterations = 8
patience = 5
step_fraction = 0.95
rule_window = 10
rule_target = 0.5
rule_factor = 5.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-1, 1]
seed = 100002
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 1000
sim_seed = 100003

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

### Your previous AGENT_STRATEGY.md
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 17 consecutive iterations with ZERO improvements
- Current weights [20.84, 10.66, 38.31] have extremely high w2 (38.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - candidate grades 4.0-4.9 vs baseline 3.544
- step_fraction=0.85 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs aggressive exploration to escape
- Current average of 3.544 with 2 games at cap is close to optimal but not good enough

## Current hypothesis
- Local optimum requires MUCH larger steps to escape
- Current step_fraction=0.85 is too conservative - ES jumping too little
- w2 (third letter weight) at 38.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- Grid search with minimal offsets should help jump to a different region of weight space
- Need to trigger the 1/5th rule to adapt step size dynamically
- Time budget is tight (59m35s used, ~1h remaining) - need to be efficient
- Increasing step_fraction to 0.95 should provide maximum exploration

## Plan for next iteration
- INCREASE step_fraction to 0.95 for maximum exploratory proposals
- REDUCE grid_offsets to [-1, 1] (only 8 evaluations before ES starts, saves time)
- Reduce max_iterations to 8 for efficiency
- Keep sim_words at 1000 for reasonable verification
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If grid search doesn't help after 8 iterations:
  - Consider even larger step_fraction (already at max 0.95)
  - Or try different seed to perturb search direction
  - Or consider reducing w2 more aggressively through grid search
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
- If still stuck after 2-3 more iterations: consider that current weights might need a complete reset or different approach

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
