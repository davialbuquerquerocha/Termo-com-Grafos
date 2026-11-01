# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Current weights [-6.0, -5.0, 3.0] are failing badly: 781 games at cap, 486 over_threshold
- Average of 10.235 guesses is very high - solver needs major improvement
- fail_penalty=2.0 was too low; failures dominate the objective
- step_fraction=0.1 is too conservative when we're far from good weights
- grid_search with 4 offsets (16 evals) is reasonable for coarse exploration
- Strategy file from previous iteration contained WRONG weight values (-9.0,-2.0,0.0) - must track actual state

## Current hypothesis
- Increase fail_penalty to 5.0 to prioritize eliminating over_threshold games
- Increase step_fraction to 0.15 for more aggressive exploration (we're far from optimal)
- Keep sim_words=2000 for fast iteration while finding good weights
- Grid search will help find direction before ES fine-tunes
- Need to find weights that solve words in ≤6 guesses consistently

## Plan for next iteration
- Monitor if fail_penalty increase reduces over_threshold games
- Watch for any improvement in average guesses (target: <6.0)
- If over_threshold approaches 0, verify on full 10589-word list
- If still failing many games, consider:
  - Increasing step_fraction further to explore more
  - Adjusting grid_offsets to different ranges
  - Checking if weight space needs different initialization
- Once over_threshold=0 on sample, validate on full list before stopping
- If no progress after 15-20 iterations, consider changing strategy entirely
