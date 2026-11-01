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
step_fraction = 0.15
rule_window = 10
rule_target = 0.5
rule_factor = 1.2
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-3, -1, 1, 3]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
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

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Current weights [-6.0, -5.0, 3.0] are failing badly: 781 games at cap, 486 over_threshold
- Average of 10.235 guesses is very high - solver needs major improvement
- fail_penalty=2.0 was too low; failures dominate the objective
- step_fraction=0.1 is too conservative when we're far from good weights
- grid_search with 4 offsets (16 evals) is reasonable for coarse exploration
- Strategy file from previous iteration contained WRONG weight values (-9.0,-2.0,0.0) - must track actual state

## Current hypothesis
- Increase fail_penalty to 5.0 to prioritize eliminating over_threshold games
- Increase step_fraction to 0.15 for more aggressive exploration (we're far from optimal)
- Keep sim_words=2000 for fast iteration while finding good weights
- Grid search will help find direction before ES fine-tunes
- Need to find weights that solve words in ≤6 guesses consistently

## Plan for next iteration
- Monitor if fail_penalty increase reduces over_threshold games
- Watch for any improvement in average guesses (target: <6.0)
- If over_threshold approaches 0, verify on full 10589-word list
- If still failing many games, consider:
  - Increasing step_fraction further to explore more
  - Adjusting grid_offsets to different ranges
  - Checking if weight space needs different initialization
- Once over_threshold=0 on sample, validate on full list before stopping
- If no progress after 15-20 iterations, consider changing strategy entirely
```