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
