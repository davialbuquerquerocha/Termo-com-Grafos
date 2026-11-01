# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES completely stuck since iteration 6 - 14 consecutive iterations with ZERO improvements
- Current weights [0.843, 0.658, 8.314] have extremely high w2 (8.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - candidate grades 4.2-4.8 vs baseline 3.593
- step_fraction=0.45 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample is too easy - success claims keep failing full list verification
- The optimizer is trapped in a local minimum and needs aggressive exploration

## Current hypothesis
- Local optimum requires MUCH larger steps to escape
- Current step_fraction=0.45 is too conservative - ES jumping too little
- w2 (third letter weight) at 8.31 is likely the main problem - needs to be reduced
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- Grid search should help jump to a different region of weight space
- Need to trigger the 1/5th rule to adapt step size dynamically

## Plan for next iteration
- INCREASE step_fraction to 0.60 for much more aggressive, exploratory proposals
- ENABLE grid_search=true with offsets [-20, -10, 0, 10, 20] to jump to different regions
- Increase rule_target to 0.5 to trigger step growth more frequently when we succeed
- Increase rule_factor to 5.0 for faster step adaptation when we succeed
- REDUCE max_iterations to 15 to save time (we're stuck, need to be efficient)
- Keep sim_words at 1000 for reasonable verification
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If grid search doesn't help after 15 iterations:
  - Consider even larger step_fraction (0.70+)
  - Or try different seed to perturb search direction
  - Or consider reducing w2 more aggressively through grid search
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
