# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 21+ consecutive iterations with ZERO improvements
- Current weights [11.43, 3.22, 38.26] have extremely high w2 (38.26) - likely over-penalizing 3rd letter matches
- Last 6 ES proposals ALL FAILED - candidate grades 3.503 vs baseline 3.113
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=300 sample shows 1 game_at_or_over_cap (marim) - sample is NOT easy enough
- The optimizer is trapped and needs AGGRESSIVE exploration to escape
- games_at_or_over_cap = 1 is the main blocker - must reach 0 for success
- Grid search is disabled (good decision) - saves evaluations before ES starts
- Need to trigger 1/5th rule to adapt step size - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid search is disabled - good decision to save time for ES iterations
- w2 (third letter weight) at 38.26 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size - need more successes to trigger it
- Time budget is tight (~1h used, ~1h remaining) - need to be efficient with iterations
- Reducing sim_words to 300 will allow more iterations in same time budget for exploration
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - lower rule_target to make it easier
- rule_factor needs to be higher to allow larger steps when successes occur

## Plan for next iteration
- Keep grid_search = false - 125 evaluations is too expensive before ES starts
- Keep sim_words = 300 - allows more iterations in same time budget
- Keep max_iterations = 15 - more chances to find improvement
- Keep patience = 8 - don't stop too early
- Keep rule_window = 2 - check adaptation more frequently
- REDUCE rule_target to 0.01 - very lenient so 1/5th rule triggers faster with fewer successes
- INCREASE rule_factor to 3.0 - larger step growth when successes occur to escape local optimum
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

### Key changes from previous iteration:
1. Kept grid_search = false - saves 125 evaluations before ES starts
2. Kept sim_words = 300 - more iterations in same time budget
3. Kept max_iterations = 15 - more chances to find improvement
4. Kept patience = 8 - don't stop too early
5. REDUCED rule_target from 0.02 to 0.01 - easier to trigger 1/5th rule
6. INCREASED rule_factor from 2.5 to 3.0 - larger step growth when successes occur
7. Kept step_fraction at 0.95 - maximum exploration
8. Kept fail_penalty at 5.0 - avoiding failures is priority

### Why this approach:
- The optimizer is completely stuck - need to save time for ES iterations
- Disabling grid search avoids wasting evaluations before ES starts
- Smaller sim_words allows more iterations in same time budget
- Lower rule_target makes 1/5th rule trigger easier for step adaptation
- Higher rule_factor allows larger steps when successes occur to escape local optimum
- More iterations = more chances to escape local optimum
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
- games_at_or_over_cap = 1 is the main blocker - must reach 0 for success
- 21+ consecutive iterations with zero improvements - need aggressive exploration
- Time budget is tight - need to be efficient with each iteration

### Next steps
- Focus on triggering 1/5th rule with lower rule_target
- Allow larger step growth with higher rule_factor to escape local optimum
- Monitor if any improvement occurs in next iterations
- If games_at_or_over_cap reaches 0 on sample, verify on full list immediately
