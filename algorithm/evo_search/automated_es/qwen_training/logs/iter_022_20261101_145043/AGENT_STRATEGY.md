# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 16 consecutive iterations with ZERO improvements
- Current weights [15.84, 5.66, 33.31] have extremely high w2 (33.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - candidate grades 4.2-4.8 vs baseline 3.545
- step_fraction=0.75 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs aggressive exploration to escape
- Current average of 3.545 with 2 games at cap is close to optimal but not good enough

## Current hypothesis
- Local optimum requires MUCH larger steps to escape
- Current step_fraction=0.75 is too conservative - ES jumping too little
- w2 (third letter weight) at 33.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- Grid search should help jump to a different region of weight space
- Need to trigger the 1/5th rule to adapt step size dynamically
- Time budget is tight (58m31s used, ~1h20m remaining) - need to be efficient
- Increasing step_fraction to 0.85 should provide more aggressive exploration

## Plan for next iteration
- INCREASE step_fraction to 0.85 for much more aggressive, exploratory proposals
- Keep grid_search with minimal offsets [-5, 0, 5] (27 evaluations) to avoid wasting time
- Keep max_iterations at 10 for efficiency
- Keep sim_words at 1000 for reasonable verification
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Increase rule_window to 10 to gather more data before adapting step size
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If grid search doesn't help after 10 iterations:
  - Consider even larger step_fraction (0.90+)
  - Or try different seed to perturb search direction
  - Or consider reducing w2 more aggressively through grid search
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
- If still stuck: consider that current weights might need a complete reset or different approach
