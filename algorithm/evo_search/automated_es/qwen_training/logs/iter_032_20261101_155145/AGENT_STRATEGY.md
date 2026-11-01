# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in deep local optimum since iteration 6 - 26+ consecutive iterations with ZERO improvements
- Current weights [7.73, -3.29, 44.52] have extremely high w2 (44.52) - likely over-penalizing 3rd letter matches
- Last 10 ES proposals ALL FAILED - candidate grades 3.09-3.22 vs baseline 3.09
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck and SHRINKING every rule_window
- sim_words=300 sample shows 0 games_at_or_over_cap - but full list verification fails consistently
- The optimizer is completely trapped and needs AGGRESSIVE exploration to escape
- CRITICAL: With 0 successes, the step size SHRINKS every rule_window iterations - this is the trap!
- Time budget is tight (~1h06m used, ~2h54m remaining) - need to be efficient with iterations

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid search is now ENABLED - will do coarse sweep around current weights before ES starts
- w2 (third letter weight) at 44.52 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size - need MORE successes to trigger it
- Time budget is tight (~1h06m used, ~2h54m remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - lower rule_target to make it easier
- rule_factor needs to be higher to allow larger steps when successes occur
- CRITICAL FIX: Increased rule_window from 2 to 4 to reduce frequency of step shrinking when no successes

## Plan for next iteration
- Enable grid_search = true with short offset list [-0.3, 0.0, 0.3] - coarse sweep around current weights
- Keep sim_words = 300 - allows more iterations in same time budget
- Keep max_iterations = 15 - more chances to find improvement
- Keep patience = 10 - don't stop too early
- LOWER rule_target from 0.005 to 0.003 - even more lenient so 1/5th rule triggers faster with fewer successes
- Keep rule_window = 4 - check adaptation less frequently to avoid shrinking too often
- Keep rule_factor at 3.0 - larger step growth when successes occur to escape local optimum
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

### Key changes from previous iteration:
1. ENABLED grid_search = true with 3 offsets [-0.3, 0.0, 0.3] - coarse sweep around current weights before ES starts
2. LOWERED rule_target from 0.005 to 0.003 - even more lenient to trigger 1/5th rule with fewer successes
3. Kept max_iterations at 15 - more chances to find improvement
4. Kept step_fraction at 0.95 - maximum exploration
5. Kept fail_penalty at 5.0 - avoiding failures is priority

### Why this approach:
- The optimizer is completely stuck - need to explore different weight regions
- Enabling grid search allows coarse sweep around current weights before ES starts (27 evaluations)
- Smaller sim_words allows more iterations in same time budget
- Lower rule_target makes 1/5th rule trigger easier for step adaptation
- Higher rule_window reduces frequency of step shrinking when no successes occur (critical!)
- Higher rule_factor allows larger steps when successes occur to escape local optimum
- More iterations = more chances to escape local optimum
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Orchestrator notices
- your success claim FAILED verification on the full list - the sample was too easy; keep improving with bigger samples or better parameters
- games_at_or_over_cap = 0 on sample but full list verification fails - need better weights
- 26+ consecutive iterations with zero improvements - need aggressive exploration
- Time budget is tight - need to be efficient with each iteration

### Next steps
- Focus on triggering 1/5th rule with lower rule_target and less frequent checks (higher rule_window)
- Allow larger step growth with higher rule_factor to escape local optimum
- Monitor if any improvement occurs in next iterations
- If games_at_or_over_cap reaches 0 on sample, verify on full list immediately
- If stuck again, consider increasing sim_words to 500-1000 for more representative sampling
- CRITICAL: If step keeps shrinking, we may need to accept that we're in a deep local optimum and try a completely different weight region
- Grid search will explore [-0.3, 0.0, 0.3] offsets around current weights - this may find better starting region
- If grid search finds improvement, ES will continue from better weights
- If grid search fails, ES will still try to find improvements with current weights

### Risk assessment
- Grid search costs 27 evaluations before ES starts - could burn time budget
- If grid search fails to find improvement, we may still be stuck
- Lower rule_target (0.003) is very lenient - may not trigger if success rate stays at 0
- Need to monitor if any improvement occurs - if not, may need to try different approach
- Time budget is tight - need to be conservative with grid search offsets
- Consider reducing grid_offsets to 2 values if time becomes critical
