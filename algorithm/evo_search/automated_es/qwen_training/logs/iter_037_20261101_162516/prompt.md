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
## Iteration 37 of at most 500
Cumulative training time so far: 1h08m51s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 3.09,
  "worst_word": "amial",
  "worst_attempts": 5,
  "over_threshold": 0,
  "games_at_or_over_cap": 0,
  "max_guesses": 6,
  "words_evaluated": 300,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 49,
    "3": 178,
    "4": 66,
    "5": 6
  },
  "weights": [
    7.730457948621313,
    -3.287924469827101,
    44.52047416663182
  ],
  "iterations_run": 15
}

### Measured compute cost of the last simulation
(no simulation has run yet)

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
  23 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   0m29s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  24 | 3.208 | azote            |     0 |   6 |       500 |    0 |   1m11s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  25 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   1m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  26 | 3.544 | miojo            |     2 |   6 |      1000 |    0 |   3m56s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  27 | 3.113 | marim            |     1 |   6 |       300 |    0 |   0m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  28 | 3.100 | amial            |     0 |   6 |       300 |    0 |   0m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  29 | 3.100 | amial            |     0 |   6 |       300 |    0 |   0m03s | your reply had no strategy block; the previous AGENT_STRATEGY.md was kept; your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  30 | 3.090 | amial            |     0 |   6 |       300 |    0 |   0m04s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  31 | 3.090 | amial            |     0 |   6 |       300 |    0 |   0m03s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  32 | 3.090 | amial            |     0 |   6 |       300 |    0 |   1m59s | parameters parse errors: ["line 18: grid_offsets: invalid literal for int() with base 10: '-0.3'"]; your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  33 | 3.090 | amial            |     0 |   6 |       300 |    0 |   0m09s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  34 | 3.090 | amial            |     0 |   6 |       300 |    0 |   0m03s | your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  35 | 3.090 | amial            |     0 |   6 |       300 |    0 |   0m04s | your reply had no strategy block; the previous AGENT_STRATEGY.md was kept; your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
  36 | 3.090 | amial            |     0 |   6 |       300 |    ? |   0m00s | your reply had no strategy block; the previous AGENT_STRATEGY.md was kept; run skipped: your parameters are identical to the last run (time is a cost) - change something to trigger a new simulation

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,3.090000,5.130000,amial,5,0,finja,75,24,7.730457948621313,-3.287924469827101,44.52047416663182
2,3.090000,3.270000,amial,5,0,cacem,6,0,7.730457948621313,-3.287924469827101,44.52047416663182
3,3.090000,3.186667,amial,5,0,zinga,7,1,7.730457948621313,-3.287924469827101,44.52047416663182
4,3.090000,3.376667,amial,5,0,adela,5,0,7.730457948621313,-3.287924469827101,44.52047416663182
5,3.090000,3.263333,amial,5,0,acaja,5,0,7.730457948621313,-3.287924469827101,44.52047416663182
6,3.090000,3.286667,amial,5,0,zinga,7,1,7.730457948621313,-3.287924469827101,44.52047416663182
7,3.090000,3.406667,amial,5,0,canzo,5,0,7.730457948621313,-3.287924469827101,44.52047416663182
8,3.090000,3.903333,amial,5,0,zinga,7,1,7.730457948621313,-3.287924469827101,44.52047416663182
9,3.090000,3.543333,amial,5,0,curta,6,0,7.730457948621313,-3.287924469827101,44.52047416663182
10,3.090000,3.493333,amial,5,0,canzo,5,0,7.730457948621313,-3.287924469827101,44.52047416663182
11,3.090000,3.350000,amial,5,0,aioli,5,0,7.730457948621313,-3.287924469827101,44.52047416663182
12,3.090000,4.536667,amial,5,0,zinga,31,16,7.730457948621313,-3.287924469827101,44.52047416663182
13,3.090000,3.213333,amial,5,0,cacem,6,0,7.730457948621313,-3.287924469827101,44.52047416663182
14,3.090000,3.236667,amial,5,0,cacem,6,0,7.730457948621313,-3.287924469827101,44.52047416663182
15,3.090000,3.196667,amial,5,0,cacem,6,0,7.730457948621313,-3.287924469827101,44.52047416663182
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
step_fraction = 0.98
rule_window = 20
rule_target = 0.2
rule_factor = 1.5
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-10, -6, -3, -1, 1, 3, 6, 10]
seed = 100001
max_guesses = 6
fail_penalty = 2.0
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
- Stuck in deep local optimum since iteration 6 - 28+ consecutive iterations with ZERO improvements
- Current weights [7.73, -3.29, 44.52] have extremely high w2 (44.52) - likely over-penalizing 3rd letter matches
- Last 10 ES proposals ALL FAILED - candidate grades 3.09-3.22 vs baseline 3.09
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck and SHRINKING every rule_window
- sim_words=300 sample shows 0 games_at_or_over_cap - but full list verification fails consistently
- The optimizer is completely trapped and needs AGGRESSIVE exploration to escape
- CRITICAL: With 0 successes, the step size SHRINKS every rule_window iterations - this is the trap!
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- grid_search costs 27 evaluations BEFORE ES starts - disabled to save budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- rule_factor needs to be higher to allow larger steps when successes occur
- CRITICAL FIX: Increased rule_window from 6 to 8 to reduce frequency of step shrinking when no successes
- grid_search disabled to save budget - ES will start immediately without 27 upfront evaluations

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid search is DISABLED - ES will start immediately without coarse sweep
- w2 (third letter weight) at 44.52 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size - need MORE successes to trigger it
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- rule_factor needs to be higher to allow larger steps when successes occur
- CRITICAL FIX: Increased rule_window from 6 to 8 to reduce frequency of step shrinking when no successes
- grid_search disabled to save budget - ES will start immediately without 27 upfront evaluations
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

## Plan for next iteration
- Disable grid_search = false - save budget, ES starts immediately without 27 upfront evaluations
- Keep sim_words = 300 - allows more iterations in same time budget
- Keep max_iterations = 15 - more chances to find improvement
- Keep patience = 10 - don't stop too early
- Keep rule_target at 0.001 - very lenient so 1/5th rule triggers faster with fewer successes
- INCREASE rule_window from 6 to 8 - check adaptation less frequently to avoid shrinking too often
- Keep rule_factor at 3.0 - larger step growth when successes occur to escape local optimum
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

### Key changes from previous iteration:
1. DISABLED grid_search = false - saves 27 evaluations before ES starts (budget preservation)
2. INCREASED rule_window from 6 to 8 - less frequent checks to avoid shrinking too often
3. Kept rule_target at 0.001 - very lenient to trigger 1/5th rule with fewer successes
4. Kept max_iterations at 15 - more chances to find improvement
5. Kept step_fraction at 0.95 - maximum exploration

### Why this approach:
- The optimizer is completely stuck - need to explore different weight regions
- Disabling grid search saves budget - ES will start immediately without 27 upfront evaluations
- Smaller sim_words allows more iterations in same time budget
- Lower rule_target makes 1/5th rule trigger easier for step adaptation
- Higher rule_window reduces frequency of step shrinking when no successes occur (critical!)
- Higher rule_factor allows larger steps when successes occur to escape local optimum
- More iterations = more chances to escape local optimum
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
- games_at_or_over_cap = 0 on sample but full list verification fails - need better weights
- 28+ consecutive iterations with zero improvements - need aggressive exploration
- Time budget is tight - need to be efficient with each iteration

### Next steps
- Focus on triggering 1/5th rule with lower rule_target (0.001) and less frequent checks (rule_window=8)
- Allow larger step growth with higher rule_factor to escape local optimum
- Monitor if any improvement occurs in next iterations
- If games_at_or_over_cap reaches 0 on sample, verify on full list immediately
- If stuck again, consider increasing sim_words to 500-1000 for more representative sampling
- CRITICAL: If step keeps shrinking, we may need to accept that we're in a deep local optimum and try a completely different weight region
- ES will start immediately without grid search overhead
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Risk assessment
- Disabled grid search saves budget - ES starts immediately without 27 upfront evaluations
- If ES fails to find improvement, we may still be stuck
- Lower rule_target (0.001) is very lenient - may not trigger if success rate stays at 0
- Need to monitor if any improvement occurs - if not, may need to try different approach
- Time budget is tight - need to be conservative with iterations
- Current w2=44.52 is suspicious - may need to be reduced significantly to escape local optimum
- If stuck again, consider reducing sim_words to 100-200 for faster iterations
- Consider increasing max_iterations to 20-25 for more exploration chances

### Orchestrator notices
- your reply had no strategy block; the previous AGENT_STRATEGY.md was kept
- run skipped: your parameters are identical to the last run (time is a cost) - change something to trigger a new simulation

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
