```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 12
patience = 8
step_fraction = 0.95
rule_window = 8
rule_target = 0.3
rule_factor = 3.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-2, -1, 0, 1, 2]
seed = 100002
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 500
sim_seed = 100003
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 17+ consecutive iterations with ZERO improvements
- Current weights [20.84, 10.66, 38.31] have extremely high w2 (38.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - candidate grades 4.0-4.9 vs baseline 3.544
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs AGGRESSIVE exploration to escape
- Current average of 3.544 with 2 games at cap is close to optimal but not good enough

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid_offsets [-1, 1] is too conservative - only 8 evaluations before ES starts
- w2 (third letter weight) at 38.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size dynamically - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 500 will allow more iterations in same time budget for exploration

## Plan for next iteration
- INCREASE grid_offsets to [-2, -1, 0, 1, 2] (125 evaluations before ES starts) to explore more regions
- REDUCE rule_target to 0.3 (more lenient) so 1/5th rule triggers faster with fewer successes
- REDUCE rule_window to 8 (check adaptation more frequently)
- INCREASE max_iterations to 12 and patience to 8 for more exploration per run
- REDUCE sim_words to 500 to allow more iterations in same time budget
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- Grid search with larger offsets should help jump to a different region of weight space
- Once grid search finds a better region, ES can refine it
- If still stuck after 12 iterations:
  - Consider even larger grid_offsets (but this costs more evaluations)
  - Or try different seed to perturb search direction
  - Or consider that current weights might need a complete reset
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 500 words, run full 10589-word validation
```