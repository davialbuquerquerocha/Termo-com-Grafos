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
patience = 3
step_fraction = 0.15
rule_window = 10
rule_target = 0.5
rule_factor = 1.2
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-5, -2, 2, 5]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 500
sim_seed = 100001

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES completely stuck for 5 iterations with no improvement at weights [-3.0, -6.0, 6.0]
- 75 over_threshold games and 211 games_at_or_over_cap indicate solver still struggles significantly
- step_fraction=0.1 was insufficient to escape local optimum
- The 1/5th success rule never triggered because no successful proposals yet
- Current weights appear trapped in a local minimum that small steps cannot escape

## Current hypothesis
- ES is in a deep local optimum at [-3.0, -6.0, 6.0] that requires larger exploration
- Need to enable grid_search to probe different weight regions before ES starts
- Larger step_fraction (0.15) combined with grid search should help escape local minimum
- Reducing sim_words to 500 allows faster iteration while searching different regions
- Grid offsets [-5, -2, 2, 5] will test 64 different starting points (4^3)

## Plan for next iteration
- Grid search will run first (64 evaluations) to find better starting weights
- Then ES will explore from the best grid point with step_fraction=0.15
- Monitor if any grid point shows improvement over current [-3.0, -6.0, 6.0]
- Watch for reduction in over_threshold games as primary success metric
- If grid search finds no improvement, consider:
  - Further increasing step_fraction to 0.20
  - Trying different grid_offsets centered around current weights
  - Increasing fail_penalty to 8.0 for more aggressive optimization
- Once over_threshold approaches 0 on 500-word sample, validate on full 10589-word list
- Keep patience=3 to avoid wasting time if stuck after grid search
- If no progress after 15 iterations, consider resetting strategy (different weight initialization approach)
```