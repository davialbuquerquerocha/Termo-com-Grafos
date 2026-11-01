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

```strategy
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
```