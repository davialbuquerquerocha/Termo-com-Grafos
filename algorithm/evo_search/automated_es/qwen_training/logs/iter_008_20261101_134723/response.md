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
step_fraction = 0.45
rule_window = 10
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
- Current weights [-1.96, -1.27, 11.50] have 91 games at or over cap on 2000-word sample
- ES has been stuck for 4+ iterations with no improvement (iter 2-4 same best_grade)
- step_fraction=0.25 was insufficient to escape local optimum around iteration 2
- Iteration 5 claimed success on 500 words but FAILED verification - sample too easy
- The 1/5th rule should adapt step size, but we need more exploration to find better weights
- Need to prioritize reducing games_at_or_over_cap (currently 91) before average
- Current step_fraction=0.35 is still not enough to escape the local optimum

## Current hypothesis
- Local optimum at [-1.96, -1.27, 11.50] requires larger exploration steps
- 0.45 step_fraction (up from 0.35) should provide enough exploration to escape
- 2000-word sample is necessary for reliable metrics before full validation
- Reducing patience to 1 prevents wasting time on non-improving runs
- The weight space needs more aggressive perturbation to find better configurations
- Increasing rule_window to 10 will give smoother step adaptation

## Plan for next iteration
- Run ES with step_fraction=0.45 to escape local minimum
- Use 2000-word sample for consistent metrics (same sim_seed for comparability)
- Reduce patience to 1 to avoid wasting iterations on stagnation
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If stuck after 10 iterations, consider:
  - Further increasing step_fraction to 0.50
  - Testing different sim_seed for new random sample
  - Temporarily increasing fail_penalty to 7.0 to prioritize failure elimination
- Once games_at_or_over_cap reaches 0 on 2000+ words, run full 10589-word validation
- Keep fail_penalty=5.0 to balance average vs failure minimization
- If ES continues to stagnate, consider manual weight perturbation or reset
```