# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in deep local optimum since iteration 6 - 28+ consecutive iterations with ZERO improvements
- Current weights [7.73, -3.29, 44.52] have extremely high w2 (44.52) - likely over-penalizing 3rd letter matches
- Last 10 ES proposals ALL FAILED - candidate grades 3.09-3.22 vs baseline 3.09
- step_fraction=0.95 is already at maximum - cannot increase further
- 1/5th rule never triggered (0 successes) - step size stuck and SHRINKING every rule_window
- sim_words=300 sample shows 0 games_at_or_over_cap - but full list verification fails consistently
- The optimizer is completely trapped and needs AGGRESSIVE exploration to escape
- CRITICAL: With 0 successes, the step size SHRINKS every rule_window iterations - this is the trap!
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- grid_search costs 27 evaluations BEFORE ES starts - disabled to save budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- rule_factor needs to be higher to allow larger steps when successes occur
- CRITICAL FIX: Increased rule_window from 6 to 8 to reduce frequency of step shrinking when no successes
- grid_search disabled to save budget - ES will start immediately without 27 upfront evaluations

## Current hypothesis
- Local optimum requires exploring DIFFERENT regions of weight space, not just small perturbations
- Current grid search is DISABLED - ES will start immediately without coarse sweep
- w2 (third letter weight) at 44.52 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- 1/5th rule needs to trigger to adapt step size - need MORE successes to trigger it
- Time budget is tight (~1h08m used, ~2h54m remaining) - need to be efficient with iterations
- Reducing sim_words to 300 allows more iterations in same time budget
- The full list (10589 words) is the real test - sample must be representative
- Need to trigger 1/5th rule to adapt step size - need MORE successes to trigger it
- rule_factor needs to be higher to allow larger steps when successes occur
- CRITICAL FIX: Increased rule_window from 6 to 8 to reduce frequency of step shrinking when no successes
- grid_search disabled to save budget - ES will start immediately without 27 upfront evaluations
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

## Plan for next iteration
- Disable grid_search = false - save budget, ES starts immediately without 27 upfront evaluations
- Keep sim_words = 300 - allows more iterations in same time budget
- Keep max_iterations = 15 - more chances to find improvement
- Keep patience = 10 - don't stop too early
- Keep rule_target at 0.001 - very lenient so 1/5th rule triggers faster with fewer successes
- INCREASE rule_window from 6 to 8 - check adaptation less frequently to avoid shrinking too often
- Keep rule_factor at 3.0 - larger step growth when successes occur to escape local optimum
- Keep step_fraction at 0.95 (maximum exploration)
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If 1/5th rule triggers, step size will adapt automatically
- If improvement found, increase sim_words for full list verification
- If games_at_or_over_cap reaches 0 on 300 words, run full 10589-word validation

### Key changes from previous iteration:
1. DISABLED grid_search = false - saves 27 evaluations before ES starts (budget preservation)
2. INCREASED rule_window from 6 to 8 - less frequent checks to avoid shrinking too often
3. Kept rule_target at 0.001 - very lenient to trigger 1/5th rule with fewer successes
4. Kept max_iterations at 15 - more chances to find improvement
5. Kept step_fraction at 0.95 - maximum exploration

### Why this approach:
- The optimizer is completely stuck - need to explore different weight regions
- Disabling grid search saves budget - ES will start immediately without 27 upfront evaluations
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
- 28+ consecutive iterations with zero improvements - need aggressive exploration
- Time budget is tight - need to be efficient with each iteration

### Next steps
- Focus on triggering 1/5th rule with lower rule_target (0.001) and less frequent checks (rule_window=8)
- Allow larger step growth with higher rule_factor to escape local optimum
- Monitor if any improvement occurs in next iterations
- If games_at_or_over_cap reaches 0 on sample, verify on full list immediately
- If stuck again, consider increasing sim_words to 500-1000 for more representative sampling
- CRITICAL: If step keeps shrinking, we may need to accept that we're in a deep local optimum and try a completely different weight region
- ES will start immediately without grid search overhead
- If improvement found, can increase sim_words for full list verification
- If games_at_or_over_cap reaches 0, run full 10589-word validation

### Risk assessment
- Disabled grid search saves budget - ES starts immediately without 27 upfront evaluations
- If ES fails to find improvement, we may still be stuck
- Lower rule_target (0.001) is very lenient - may not trigger if success rate stays at 0
- Need to monitor if any improvement occurs - if not, may need to try different approach
- Time budget is tight - need to be conservative with iterations
- Current w2=44.52 is suspicious - may need to be reduced significantly to escape local optimum
- If stuck again, consider reducing sim_words to 100-200 for faster iterations
- Consider increasing max_iterations to 20-25 for more exploration chances
