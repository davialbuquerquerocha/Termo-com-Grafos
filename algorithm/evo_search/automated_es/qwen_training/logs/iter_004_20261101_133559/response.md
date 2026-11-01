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
step_fraction = 0.10
rule_window = 10
rule_target = 0.5
rule_factor = 1.2
min_step_fraction = 0.001
grid_search = false
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
- ES is completely stuck for 5 iterations with no improvement - all candidates worse than best
- Current weights [-3.0, -6.0, 6.0] in a local optimum that small steps (0.05) cannot escape
- 75 over_threshold games and 211 games_at_or_over_cap - solver still struggles significantly
- The 1/5th success rule hasn't triggered any step adaptation because no success yet
- Step size of 0.05 is too conservative - making tiny steps that don't find improvements

## Current hypothesis
- step_fraction=0.05 is too small; ES is trapped in local optimum making micro-steps
- Need to increase step_fraction to 0.10 to make bigger exploratory jumps
- This should help ES escape the current local optimum and find better weight regions
- Reducing max_iterations and patience will prevent wasting time if still stuck
- fail_penalty=5.0 is correctly prioritizing elimination of over_threshold games

## Plan for next iteration
- Monitor if larger step_fraction (0.10) allows ES to escape local optimum
- Watch for ANY improvement in average guesses or reduction in over_threshold
- If still stuck after 3 iterations with step_fraction=0.10, consider:
  - Further increasing step_fraction to 0.15
  - Enabling grid_search=true with shorter offsets to find better starting weights
  - Increasing fail_penalty to 10.0 to more aggressively penalize failures
- Once over_threshold approaches 0 on sample, validate on full 10589-word list
- If no progress after 15-20 iterations, consider changing strategy entirely (e.g., different weight initialization)
- Keep sim_words=2000 for speed while searching
```