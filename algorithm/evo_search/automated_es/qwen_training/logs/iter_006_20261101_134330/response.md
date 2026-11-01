```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source list"
# =====================================================================

max_iterations = 10
patience = 2
step_fraction = 0.25
rule_window = 8
rule_target = 0.6
rule_factor = 1.3
min_step_fraction = 0.001
grid_search = false
grid_offsets = [-3, 3]
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
- Current weights [-1.0, -4.0, 11.0] show 0 over_threshold but 4 games_at_or_over_cap on 500-word sample
- Success claim FAILED verification on full 10589-word list - sample was too easy
- ES has been stuck with no improvement for 3+ iterations
- step_fraction=0.15 was insufficient to escape local optimum
- grid_search with 4 offsets (64 evaluations) is too expensive and slows progress
- Need larger step size and bigger sample for reliable validation

## Current hypothesis
- Local optimum at [-1.0, -4.0, 11.0] requires larger exploration steps
- 0.25 step_fraction should provide enough exploration to find better weights
- 2000-word sample is more representative than 500 while still fast enough
- Disabling grid_search avoids expensive 64-evaluation overhead
- Need to reach 0 games_at_or_over_cap on full list before claiming success

## Plan for next iteration
- Run ES with step_fraction=0.25 to escape local minimum
- Use 2000-word sample for more reliable metrics before full validation
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If stuck after 10 iterations, consider:
  - Further increasing step_fraction to 0.30
  - Testing different weight initialization (not weights themselves)
  - Reducing patience to 1 to avoid wasted time
- Once 0 games_at_or_over_cap on 2000+ words, run full 10589-word validation
- Keep fail_penalty=5.0 to balance average vs failure minimization
- If ES continues to stagnate, consider manual weight perturbation or reset
```