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
step_fraction = 0.75
rule_window = 10
rule_target = 0.5
rule_factor = 1.5
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
- Stuck at iteration 9 with no improvement since iteration 2 (7+ iterations stagnant)
- Current weights [-1.96, -1.27, 11.50] produce 91 games at or over cap on 2000-word sample
- step_fraction=0.60 was insufficient to escape local optimum
- 1/5th rule hasn't triggered growth due to low success rate (~95.5% success)
- Average (3.913) is decent but games_at_or_over_cap (91) is the blocking factor
- Need more aggressive exploration to find weights that solve all words within 6 guesses
- Lower rule_target helps trigger step growth earlier when we find improvements

## Current hypothesis
- Local optimum requires larger exploration steps (step_fraction=0.75)
- rule_target=0.5 will allow step growth more easily when we find improvements
- The current weight region needs bigger jumps to escape
- 2000-word sample with fixed sim_seed ensures comparable metrics
- fail_penalty=5.0 balances average vs failure minimization appropriately
- Current step size may be too conservative for this difficult optimization landscape

## Plan for next iteration
- Run ES with step_fraction=0.75 for more aggressive exploration
- Use rule_target=0.5 to trigger step growth when success rate exceeds 50%
- Keep rule_factor=1.5 for fast step growth when we succeed
- Maintain sim_words=2000 and sim_seed=100001 for consistent comparison
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If still stuck after 10 iterations, consider:
  - Further increasing step_fraction to 0.80-0.85
  - Testing different sim_seed for fresh random sample
  - Complete reset with different initial weights if needed
- Once games_at_or_over_cap reaches 0 on 2000+ words, run full 10589-word validation
- Keep patience=1 to avoid wasting iterations on non-improving runs
- If ES continues to stagnate, consider manual weight perturbation or complete reset
```