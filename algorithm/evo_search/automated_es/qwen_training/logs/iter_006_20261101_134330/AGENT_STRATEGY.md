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
