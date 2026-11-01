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
step_fraction = 0.1
rule_window = 10
rule_target = 0.5
rule_factor = 1.2
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-3, -1, 1, 3]
seed = 100001
max_guesses = 6
fail_penalty = 2.0
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
- Current weights (w0=-9.0, w1=-2.0, w2=0.0) already achieve 0 over_threshold games on 2000-word sample
- Best average is 2.125 guesses - room for improvement
- step_fraction = 0.98 was too aggressive (98% of weight norm = huge jumps)
- grid_search with 8 offsets (512 evaluations) is wasteful when we already have good results
- Need to verify zero failures on full 10589-word list before stopping

## Current hypothesis
- Reduce step_fraction to 0.1 for more stable, fine-grained exploration
- Reduce grid_search offsets to 4 values (16 evaluations) to save compute
- Increase rule_target to 0.5 since we're already at 100% success rate
- Keep sim_words=2000 for fast iterations while refining weights
- Once stable weights found, verify on full list before finalizing

## Plan for next iteration
- Run with reduced step_fraction to explore local improvements around current weights
- Monitor if we can reduce average from 2.125 to ~2.0 or lower
- If success rate stays at 100%, consider increasing sim_words to verify on larger sample
- Watch for any increase in over_threshold games - if they appear, increase fail_penalty or adjust weights
- Prepare to switch to full word list (sim_words=0) once we have stable, zero-failure weights
- If no improvement after 10-15 iterations, consider changing strategy (different weight space exploration)
```