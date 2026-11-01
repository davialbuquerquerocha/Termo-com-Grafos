```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 10
patience = 6
step_fraction = 0.95
rule_window = 5
rule_target = 0.1
rule_factor = 2.5
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-1, 0, 1]
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

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 19+ consecutive iterations with ZERO improvements
- Current weights [18.84, 8.66, 39.31] have extremely high w2 (39.31) - likely over-penalizing 3rd letter matches
- Last 8 ES proposals ALL FAILED - candidate grades 3.3-4.0 vs baseline 3.208
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=500 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs AGGRESSIVE exploration to escape
- Current average of 3.208 with 0 games at cap on 500 words is good but sample is too small

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid_offsets [-1, 0, 1] (27 evaluations) is better than [-2,-1,0,1,2] (125 evaluations)
- w2 (third letter weight) at 39.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size dynamically - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 1000 will allow more iterations in same time budget for exploration
- The full list (10589 words) is the real test - sample must be representative

## Plan for next iteration
- REDUCE grid_offsets to [-1, 0, 1] (27 evaluations before ES starts) - less expensive than 125
- REDUCE rule_window to 5 (check adaptation more frequently)
- REDUCE rule_target to 0.1 (more lenient) so 1/5th rule triggers faster with fewer successes
- REDUCE max_iterations to 10 and patience to 6 for more iterations in same time budget
- INCREASE sim_words to 1000 to get more representative sample (still fast enough)
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- Grid search with smaller offsets should help jump to a different region of weight space
- Once grid search finds a better region, ES can refine it
- If still stuck after 10 iterations:
  - Consider even smaller grid_offsets (just [0])
  - Or try different seed to perturb search direction
  - Or consider that current weights might need a complete reset
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation

### Key changes from previous iteration:
1. Reduced grid_offsets from 5 values to 3 values (125→27 evals) - saves ~88% of grid cost
2. Reduced rule_window from 8 to 5 - more frequent step adaptation
3. Reduced rule_target from 0.3 to 0.1 - easier to trigger 1/5th rule
4. Increased sim_words from 500 to 1000 - more representative sample
5. Reduced max_iterations from 12 to 10 - more iterations in same time budget
6. Reduced patience from 8 to 6 - stop early if no improvement
```