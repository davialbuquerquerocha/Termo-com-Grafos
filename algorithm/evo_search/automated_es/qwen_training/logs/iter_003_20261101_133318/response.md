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
step_fraction = 0.05
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
- ES has been stuck for 5 iterations with no improvement (all candidates worse than best)
- Current weights [-3.0, -6.0, 6.0] are not finding improvements with step_fraction=0.15
- 75 over_threshold games and 211 games_at_or_over_cap indicate solver still struggles
- Large step size (0.15) is causing random walks without finding local optimum
- Need smaller, more careful steps to explore weight space locally

## Current hypothesis
- step_fraction=0.15 is too aggressive; ES is jumping over the optimum
- Reducing to 0.05 will make smaller, more careful local search steps
- This should allow ES to find improvements in the current weight neighborhood
- fail_penalty=5.0 correctly prioritizes eliminating over_threshold games
- Grid search already completed (we're at iteration 3), so disable it to save evaluations

## Plan for next iteration
- Monitor if smaller step_fraction allows ES to find improvements
- Watch for reduction in over_threshold games (target: <50)
- If still stuck after 5 iterations with step_fraction=0.05, consider:
  - Further reducing step_fraction to 0.02
  - Increasing fail_penalty to 10.0 to more aggressively penalize failures
  - Checking if weight initialization needs adjustment
- Once over_threshold approaches 0 on sample, validate on full 10589-word list
- If no progress after 15-20 iterations, consider changing strategy entirely
- Keep sim_words=2000 for speed while searching
```