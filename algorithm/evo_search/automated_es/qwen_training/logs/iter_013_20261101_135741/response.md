```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 20
patience = 3
step_fraction = 1.0
rule_window = 5
rule_target = 0.3
rule_factor = 3.0
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
sim_seed = 100003
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 (7+ iterations with no improvement)
- Current weights [-1.96, -1.27, 11.50] produce 118 games at/over cap on 2000-word sample
- ES candidates consistently worse than current best (12.76 vs 3.94)
- step_fraction=1.0 already at maximum but still not escaping
- 1/5th rule never triggered growth due to no improvements
- Average (3.94) is acceptable but games_at_or_over_cap (118) is the blocking factor
- Need to escape current weight region to find weights solving all words in ≤6 guesses

## Current hypothesis
- Local optimum trap requires coarse exploration before fine tuning
- ES stuck refining around bad weights; need to jump to better region first
- Grid search with offsets [-5,-2,2,5] will probe around current weights
- Smaller sim_words (500) will find improvements faster, then validate on full list
- More aggressive rule parameters (rule_target=0.3, rule_factor=3.0) will grow step faster when we succeed
- Increased max_iterations (20) and patience (3) will allow more exploration per run
- Fresh sim_seed (100003) will give different random sample

## Plan for next iteration
- Enable grid_search=true with 4 offsets to explore coarse space first
- Reduce sim_words to 500 for faster iteration cycles (find improvements quickly)
- Keep step_fraction=1.0 for maximum exploration
- Adjust rule parameters: rule_target=0.3 (easier to trigger growth), rule_factor=3.0 (faster growth)
- Increase max_iterations to 20 to allow more proposals per run
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If grid search finds better region, ES will continue from there
- Once games_at_or_over_cap reaches 0 on 500 words, run full 10589-word validation
- If still stuck after 20 iterations, consider:
  - Further reducing sim_words to 200 for faster cycles
  - Complete reset with different initial weights
  - Manual weight perturbation based on analysis of worst words
- Keep patience=3 to maximize iterations per run
- If ES continues to stagnate, consider complete reset with fresh weights
```