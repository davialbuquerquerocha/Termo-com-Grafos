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
