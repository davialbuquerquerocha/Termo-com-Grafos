# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES completely stuck for 5 iterations with no improvement at weights [-3.0, -6.0, 6.0]
- 75 over_threshold games and 211 games_at_or_over_cap indicate solver still struggles significantly
- step_fraction=0.1 was insufficient to escape local optimum
- The 1/5th success rule never triggered because no successful proposals yet
- Current weights appear trapped in a local minimum that small steps cannot escape

## Current hypothesis
- ES is in a deep local optimum at [-3.0, -6.0, 6.0] that requires larger exploration
- Need to enable grid_search to probe different weight regions before ES starts
- Larger step_fraction (0.15) combined with grid search should help escape local minimum
- Reducing sim_words to 500 allows faster iteration while searching different regions
- Grid offsets [-5, -2, 2, 5] will test 64 different starting points (4^3)

## Plan for next iteration
- Grid search will run first (64 evaluations) to find better starting weights
- Then ES will explore from the best grid point with step_fraction=0.15
- Monitor if any grid point shows improvement over current [-3.0, -6.0, 6.0]
- Watch for reduction in over_threshold games as primary success metric
- If grid search finds no improvement, consider:
  - Further increasing step_fraction to 0.20
  - Trying different grid_offsets centered around current weights
  - Increasing fail_penalty to 8.0 for more aggressive optimization
- Once over_threshold approaches 0 on 500-word sample, validate on full 10589-word list
- Keep patience=3 to avoid wasting time if stuck after grid search
- If no progress after 15 iterations, consider resetting strategy (different weight initialization approach)
