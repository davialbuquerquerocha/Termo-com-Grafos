```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 10
patience = 1
step_fraction = 0.90
rule_window = 10
rule_target = 0.3
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
sim_seed = 100001

# LOCKED paths (relative to evo_search2.py; empty = auto-detect ../dataset)
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck at iteration 10 with no improvement since iteration 6 (4+ iterations stagnant)
- Current weights [-1.96, -1.27, 11.50] produce 91 games at or over cap on 2000-word sample
- step_fraction=0.75 was insufficient to escape local optimum
- 1/5th rule hasn't triggered growth because success rate is high (~95.5%) but we're not improving
- Average (3.913) is decent but games_at_or_over_cap (91) is the blocking factor
- ES needs more aggressive exploration to escape this local optimum
- The current weight region is a trap - we need bigger jumps to find better weights

## Current hypothesis
- Local optimum requires larger exploration steps (step_fraction=0.90)
- rule_target=0.3 will allow step growth more easily when we find improvements
- rule_factor=2.0 will accelerate step growth when we succeed
- The current step size is too conservative for this difficult optimization landscape
- Need to escape the current weight region to find weights that solve all words within 6 guesses
- 2000-word sample with fixed sim_seed ensures comparable metrics

## Plan for next iteration
- Run ES with step_fraction=0.90 for more aggressive exploration
- Use rule_target=0.3 to trigger step growth when success rate exceeds 30%
- Use rule_factor=2.0 for faster step growth when we succeed
- Maintain sim_words=2000 and sim_seed=100001 for consistent comparison
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If still stuck after 10 iterations, consider:
  - Further increasing step_fraction to 0.95
  - Testing different sim_seed for fresh random sample
  - Complete reset with different initial weights if needed
- Once games_at_or_over_cap reaches 0 on 2000+ words, run full 10589-word validation
- Keep patience=1 to avoid wasting iterations on non-improving runs
- If ES continues to stagnate, consider manual weight perturbation or complete reset
```