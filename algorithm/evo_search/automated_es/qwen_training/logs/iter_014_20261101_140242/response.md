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

```strategy
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
```