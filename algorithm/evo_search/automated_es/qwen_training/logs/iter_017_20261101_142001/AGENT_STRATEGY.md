# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES stuck in local optimum since iteration 6 (10+ iterations with no improvement)
- Current weights [3.04, 0.73, 9.50] produce 13 games at/over cap on 1000-word sample
- All 5 ES candidates in last iteration were WORSE than current best (3.63 avg)
- step_fraction=1.0 was TOO LARGE - made proposals too aggressive, missing local optimum
- 1/5th rule never triggered because no successes to count
- Need smaller steps to explore local region more carefully
- Grid search disabled - ES needs to explore locally with smaller steps

## Current hypothesis
- Local optimum trap requires SMALLER steps to escape, not larger
- step_fraction=1.0 was too aggressive - ES jumping too far to find improvements
- Need step_fraction=0.25 to make smaller, more careful explorations
- Lower rule_target (0.2) to trigger step growth more frequently when we succeed
- Lower rule_factor (3.0) for more gradual step adaptation
- ES needs to find a direction that reduces games_at_or_over_cap first
- Once failures drop to 0, average will naturally improve

## Plan for next iteration
- Reduce step_fraction to 0.25 for smaller, more careful exploration
- Lower rule_target to 0.2 to trigger step growth more frequently
- Lower rule_factor to 3.0 for more gradual step adaptation
- Increase max_iterations to 30 to allow more exploration with smaller steps
- Keep sim_words at 1000 for reasonable verification
- Monitor games_at_or_over_cap as primary metric (must reach 0)
- If still stuck after 30 iterations:
  - Consider increasing step_fraction slightly if ES is too conservative
  - Or try different seed to perturb search direction
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
