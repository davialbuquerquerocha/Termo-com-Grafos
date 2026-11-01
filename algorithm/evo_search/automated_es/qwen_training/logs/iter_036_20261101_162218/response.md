```parameters
# =====================================================================
# evo_search2 parameters - WRITTEN BY QWEN (the tuning agent)
# evo_search2.py reads this file on every start.
# Enforced by run_qwen_training.py:
#   * parallel_workers and every path_* key are LOCKED for Qwen
#   * max_guesses must stay <= 6
#   * sim_words = 0 means "use the whole source word list"
# =====================================================================

max_iterations = 12
patience = 10
step_fraction = 0.95
rule_window = 12
rule_target = 0.001
rule_factor = 5.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-1, 0, 1]
seed = 100002
max_guesses = 6
fail_penalty = 5.0
# LOCKED -