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
## Iteration 28 of at most 500
Cumulative training time so far: 1h06m20s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 3.113333,
  "worst_word": "marim",
  "worst_attempts": 6,
  "over_threshold": 0,
  "games_at_or_over_cap": 1,
  "max_guesses": 6,
  "words_evaluated": 300,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 49,
    "3": 175,
    "4": 66,
    "5": 8,
    "6": 1
  },
  "weights": [
    11.432933489585245,
    3.2158924688373594,
    38.26058331902591
  ],
  "iterations_run": 15
}

### Measured compute cost of the last simulation
- last simulation: 0m04s wall-clock
- measured cost: 13.6 ms per word evaluated (300 words)
- measured cost: 0.27 s per ES proposal (15 proposals)
- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
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
  24 | 3.208 | azote            |     0 |   6 |       500 |    0 |   1m11s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  25 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   1m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  26 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   3m56s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  27 | 3.113 | marim            |     1 |   6 |       300 |    0 |   0m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,3.140000,3.946667,amial,5,0,xaxim,8,13,18.843292317311434,7.657776183650277,38.31359576024953
2,3.140000,3.260000,amial,5,0,cacem,6,0,18.843292317311434,7.657776183650277,38.31359576024953
3,3.140000,3.143333,amial,5,0,amial,5,0,18.843292317311434,7.657776183650277,38.31359576024953
4,3.140000,3.340000,amial,5,0,adela,5,0,18.843292317311434,7.657776183650277,38.31359576024953
5,3.140000,3.140000,amial,5,0,amial,5,0,18.843292317311434,7.657776183650277,38.31359576024953
6,3.126667,3.126667,amial,5,0,amial,5,0,15.323078881707913,2.2580516371699693,36.92631498902771
7,3.126667,3.200000,amial,5,0,cacem,6,0,15.323078881707913,2.2580516371699693,36.92631498902771
8,3.126667,3.206667,amial,5,0,cacem,6,0,15.323078881707913,2.2580516371699693,36.92631498902771
9,3.116667,3.116667,xaxim,6,0,xaxim,6,0,16.017989370119583,7.785677715787888,39.37754293882696
10,3.116667,3.200000,xaxim,6,0,cacem,6,0,16.017989370119583,7.785677715787888,39.37754293882696
11,3.116667,3.343333,xaxim,6,0,amial,5,0,16.017989370119583,7.785677715787888,39.37754293882696
12,3.116667,3.253333,xaxim,6,0,cacem,6,0,16.017989370119583,7.785677715787888,39.37754293882696
13,3.116667,3.193333,xaxim,6,0,cacem,6,0,16.017989370119583,7.785677715787888,39.37754293882696
14,3.113333,3.113333,marim,6,0,marim,6,0,11.432933489585245,3.2158924688373594,38.26058331902591
15,3.113333,3.503333,marim,6,0,grapa,6,0,11.432933489585245,3.2158924688373594,38.26058331902591
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

max_iterations = 15
patience = 8
step_fraction = 0.95
rule_window = 2
rule_target = 0.02
rule_factor = 2.5
min_step_fraction = 0.001
grid_search = false
grid_offsets = [0]
seed = 100002
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 300
sim_seed = 100003

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

### Your previous AGENT_STRATEGY.md
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 21+ consecutive iterations with ZERO improvements
- Current weights [18.84, 7.66, 38.31] have extremely high w2 (38.31) - likely over-penalizing 3rd letter matches
- Last 6 ES proposals ALL FAILED - candidate grades 3.566-4.234 vs baseline 3.544
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps showing 2 games_at_or_over_cap - sample is NOT easy enough
- The optimizer is trapped and needs AGGRESSIVE exploration to escape
- games_at_or_over_cap = 2 is the main blocker - must reach 0 for success
- Grid search is wasting time (125 evaluations) before ES even starts
- Need to reduce sim_words to allow more iterations in remaining time budget

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid search is too expensive - disabled it to save time for ES iterations
- w2 (third letter weight) at 38.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size dynamically - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 300 will allow more iterations in same time budget for exploration
- The full list (10589 words) is the real test - sample must be representative
- Grid search disabled to avoid wasting evaluations before ES starts
- Need to trigger 1/5th rule to adapt step size - lower rule_target to make it easier

## Plan for next iteration
- DISABLE grid_search (false) - 125 evaluations is too expensive before ES starts
- REDUCE sim_words to 300 - allows more iterations in same time budget
- INCREASE max_iterations to 15 - more chances to find improvement
- INCREASE patience to 8 - don't stop too early
- REDUCE rule_window to 2 - check adaptation more frequently
- REDUCE rule_target to 0.02 - very lenient so 1/5th rule triggers faster with fewer successes
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

### Key changes from previous iteration:
1. DISABLED grid_search (false) - saves 125 evaluations before ES starts
2. REDUCED sim_words from 1000 to 300 - more iterations in same time budget
3. INCREASED max_iterations from 8 to 15 - more chances to find improvement
4. INCREASED patience from 5 to 8 - don't stop too early
5. REDUCED rule_window from 3 to 2 - more frequent step adaptation
6. REDUCED rule_target from 0.05 to 0.02 - easier to trigger 1/5th rule
7. Kept step_fraction at 0.95 - maximum exploration
8. Kept fail_penalty at 5.0 - avoiding failures is priority

### Why this approach:
- The optimizer is completely stuck - need to save time for ES iterations
- Disabling grid search avoids wasting evaluations before ES starts
- Smaller sim_words allows more iterations in same time budget
- Lower rule_target makes 1/5th rule trigger easier for step adaptation
- More iterations = more chances to escape local optimum
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Orchestrator notices
- Your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
- games_at_or_over_cap = 2 is the main blocker - must reach 0 for success
- 21+ consecutive iterations with zero improvements - need aggressive exploration
- Time budget is tight - need to be efficient with each iteration

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
