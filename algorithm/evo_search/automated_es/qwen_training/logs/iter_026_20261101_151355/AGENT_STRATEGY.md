# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 19+ consecutive iterations with ZERO improvements
- Current weights [18.84, 7.66, 38.31] have extremely high w2 (38.31) - likely over-penalizing 3rd letter matches
- Last 6 ES proposals ALL FAILED - candidate grades 3.566-4.234 vs baseline 3.544
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs AGGRESSIVE exploration to escape
- Current average of 3.544 with 2 games at cap on 1000 words is good but sample is too small

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid_offsets [-2,-1,0,1,2] (125 evaluations) is more expensive but may help jump to better region
- w2 (third letter weight) at 38.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size dynamically - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 1000 will allow more iterations in same time budget for exploration
- The full list (10589 words) is the real test - sample must be representative
- Grid search with wider offsets should help jump to a different region of weight space

## Plan for next iteration
- INCREASE grid_offsets to [-2, -1, 0, 1, 2] (125 evaluations before ES starts) - more aggressive exploration
- REDUCE rule_window to 3 (check adaptation more frequently)
- REDUCE rule_target to 0.05 (very lenient) so 1/5th rule triggers faster with fewer successes
- REDUCE max_iterations to 8 and patience to 5 for more iterations in same time budget
- Keep sim_words at 1000 to get representative sample (still fast enough)
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- Grid search with wider offsets should help jump to a different region of weight space
- Once grid search finds a better region, ES can refine it
- If still stuck after 8 iterations:
  - Consider even smaller grid_offsets (just [0])
  - Or try different seed to perturb search direction
  - Or consider that current weights might need a complete reset
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation

### Key changes from previous iteration:
1. INCREASED grid_offsets from [-1,0,1] to [-2,-1,0,1,2] (27→125 evals) - more aggressive exploration
2. REDUCED rule_window from 5 to 3 - more frequent step adaptation
3. REDUCED rule_target from 0.1 to 0.05 - easier to trigger 1/5th rule
4. REDUCED max_iterations from 10 to 8 - more iterations in same time budget
5. REDUCED patience from 6 to 5 - stop early if no improvement
6. Kept sim_words at 1000 - representative sample
7. Kept step_fraction at 0.95 - maximum exploration

### Why this approach:
- The optimizer is completely stuck - we need AGGRESSIVE exploration
- Wider grid offsets help jump to different regions of weight space
- Lower rule_target makes 1/5th rule trigger easier
- More iterations in same time budget = more chances to find improvement
- If grid search finds a better region, ES can refine it
- If still stuck, we may need to consider weight reset or different strategy
