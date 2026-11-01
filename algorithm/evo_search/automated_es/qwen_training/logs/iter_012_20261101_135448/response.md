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
step_fraction = 1.0
rule_window = 10
rule_target = 0.5
rule_factor = 2.0
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
sim_seed = 100002

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck at iteration 11 with no improvement since iteration 6 (5+ iterations stagnant)
- Current weights [-1.96, -1.27, 11.50] produce 91 games at or over cap on 2000-word sample
- step_fraction=0.9 was insufficient to escape local optimum
- ES candidate grades (18.03) are much worse than best (3.913) - ES not finding better weights
- 1/5th rule hasn't triggered growth because we're not seeing improvements
- Average (3.913) is decent but games_at_or_over_cap (91) is the blocking factor
- The current weight region is a trap - we need bigger jumps to find better weights
- With patience=1, we only get 10 iterations per run - need more iterations to find improvements

## Current hypothesis
- Local optimum requires maximum exploration (step_fraction=1.0)
- rule_target=0.5 will allow step growth more easily when we find improvements
- rule_factor=2.0 will accelerate step growth when we succeed
- The current step size was too conservative for this difficult optimization landscape
- Need to escape the current weight region to find weights that solve all words within 6 guesses
- Fresh sim_seed (100002) will give a different random sample - may help escape local optimum
- Increased patience=3 will allow more iterations per run to find improvements

## Plan for next iteration
- Run ES with step_fraction=1.0 for maximum exploration
- Use rule_target=0.5 to trigger step growth when success rate exceeds 50%
- Use rule_factor=2.0 for faster step growth when we succeed
- Maintain sim_words=2000 and sim_seed=100002 for consistent comparison
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If still stuck after 15 iterations, consider:
  - Further increasing step_fraction (already at max 1.0)
  - Testing different sim_seed for fresh random sample
  - Complete reset with different initial weights if needed
- Once games_at_or_over_cap reaches 0 on 2000+ words, run full 10589-word validation
- Keep patience=3 to maximize iterations per run and find improvements
- If ES continues to stagnate, consider manual weight perturbation or complete reset
```