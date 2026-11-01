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
## Iteration 20 of at most 500
Cumulative training time so far: 52m27s.

### Metrics of the last simulation (weights currently in pesos.csv)
{
  "average": 3.593,
  "worst_word": "acaja",
  "worst_attempts": 6,
  "over_threshold": 0,
  "games_at_or_over_cap": 8,
  "max_guesses": 6,
  "words_evaluated": 1000,
  "word_errors": 0,
  "attempts_histogram": {
    "1": 1,
    "2": 46,
    "3": 411,
    "4": 451,
    "5": 83,
    "6": 8
  },
  "weights": [
    0.8432923173114335,
    0.6577761836502781,
    8.313595760249525
  ],
  "iterations_run": 5
}

### Measured compute cost of the last simulation
- last simulation: 0m13s wall-clock
- measured cost: 13.8 ms per word evaluated (1000 words)
- measured cost: 2.76 s per ES proposal (5 proposals)
- remember: a grid sweep adds len(grid_offsets)**3 evaluations BEFORE the ES starts

### Run history (oldest first)
iter | avg   | worst            | >=cap | cap | sim_words | exit | elapsed | note
   6 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m39s | 
   7 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m24s | 
   8 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m24s | 
   9 | 3.913 | exina            |    91 |   6 |      2000 |    0 |   0m28s | 
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

### training_log.csv tail (last ES proposals; note: the columns named best_grade/candidate_grade actually store the AVERAGE guesses of best/candidate)
```
iteration,best_grade,candidate_grade,best_worst_word,best_worst_attempts,best_over_threshold,candidate_worst_word,candidate_worst_attempts,candidate_over_threshold,w0,w1,w2
1,3.593000,4.821000,acaja,6,0,zinga,27,123,0.8432923173114335,0.6577761836502781,8.313595760249525
2,3.593000,4.311000,acaja,6,0,marim,14,41,0.8432923173114335,0.6577761836502781,8.313595760249525
3,3.593000,3.769000,acaja,6,0,traze,10,20,0.8432923173114335,0.6577761836502781,8.313595760249525
4,3.593000,4.709000,acaja,6,0,zinga,26,109,0.8432923173114335,0.6577761836502781,8.313595760249525
5,3.593000,4.643000,acaja,6,0,zinga,26,97,0.8432923173114335,0.6577761836502781,8.313595760249525
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
step_fraction = 0.45
rule_window = 5
rule_target = 0.4
rule_factor = 3.0
min_step_fraction = 0.001
grid_search = false
grid_offsets = [-15, -10, 10, 15]
seed = 100001
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
- ES stuck since iteration 6 with 8-91 games at/over cap (words needing >6 guesses)
- Current weights [0.843, 0.658, 8.314] have very high w2 (8.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - no improvements found, candidates had 4.2-4.3 avg vs baseline 3.593
- step_fraction=0.35 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- ES is trapped in a local optimum and needs larger jumps to find better regions

## Current hypothesis
- Local optimum requires LARGER steps to escape, not smaller
- step_fraction=0.35 was too conservative - ES jumping too little to find improvements
- Need step_fraction=0.45 to make more aggressive explorations
- Higher rule_target (0.4) to trigger step growth more frequently when we succeed
- Higher rule_factor (3.0) for faster step adaptation when we finally succeed
- w2 (third letter weight) at 8.31 is likely the main problem - needs to be reduced
- ES needs to find direction that reduces games_at_or_over_cap first (this is lexically more important than average)

## Plan for next iteration
- Increase step_fraction to 0.45 for more aggressive, exploratory proposals
- Increase rule_target to 0.4 to trigger step growth more frequently
- Increase rule_factor to 3.0 for faster step adaptation when we succeed
- Keep max_iterations at 30 for sufficient exploration
- Keep sim_words at 1000 for reasonable verification
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If still stuck after 30 iterations:
  - Consider increasing step_fraction further to 0.55
  - Or try different seed to perturb search direction
  - Or consider grid_search=true with focused offsets around current weights
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters

Decide the next parameters, update your strategy file, and reply in the required format.
</user>
