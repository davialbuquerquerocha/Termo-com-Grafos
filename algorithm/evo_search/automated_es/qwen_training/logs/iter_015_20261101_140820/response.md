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
step_fraction = 0.5
rule_window = 5
rule_target = 0.3
rule_factor = 5.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-15, -10, 10, 15]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
# LOCKED - Qwen cannot change this (safety: CPU usage)
parallel_workers = 17

# Simulation set: 0 = every word of the source list. Start small!
sim_words = 1000
sim_seed = 100003
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 (8+ iterations with no improvement)
- Current weights [3.04, 0.73, 9.50] produce 1 game at/over cap on 500-word sample
- ES candidates consistently worse than current best (3.94 vs 3.24)
- step_fraction=1.0 was too aggressive - causing large jumps that overshoot the optimum
- 1/5th rule never triggered growth due to no improvements
- Average (3.24) is very close to success but games_at_or_over_cap (1) is blocking factor
- Sample verification fails on full list - need to ensure improvements generalize
- Grid search with [-10,-5,5,10] was insufficient - need broader exploration

## Current hypothesis
- Local optimum trap requires BOTH finer local exploration AND broader global jumps
- step_fraction=1.0 was too aggressive - we need 0.5 for precision around current weights
- Current region is a local optimum; need to jump to different region via grid search
- Larger grid_offsets [-15,-10,10,15] will probe more distant regions
- Increased sim_words to 1000 for better verification before claiming success
- Current weights are too close to optimum - need to escape via grid search first

## Plan for next iteration
- Reduce step_fraction to 0.5 for finer exploration around current weights
- Enable grid_search with 4 larger offsets to explore coarse space first
- Increase sim_words to 1000 for better verification (avoid false success claims)
- Keep rule_factor=5.0 for faster step growth when we succeed
- Keep max_iterations=30 and patience=5 for adequate exploration
- If grid search finds better region, ES will continue from there
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If still stuck after 30 iterations, consider:
  - Complete reset with different initial weights
  - Manual weight perturbation based on analysis of worst words
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If ES continues to stagnate, consider complete reset with fresh weights
```