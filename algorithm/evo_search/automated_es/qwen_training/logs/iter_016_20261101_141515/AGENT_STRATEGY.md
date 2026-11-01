# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 (10+ iterations with no improvement)
- Current weights [3.04, 0.73, 9.50] produce 13 games at/over cap on 1000-word sample
- ES candidates consistently worse than current best (3.63 avg, no improvements)
- step_fraction=0.5 was too conservative - ES not exploring enough to escape local optimum
- 1/5th rule never triggered growth due to no improvements
- Average (3.63) is close but games_at_or_over_cap (13) is the blocking factor
- Grid search disabled - ES needs to explore more broadly to find escape route
- Need to reach 0 games at/over cap on full 10589-word list

## Current hypothesis
- Local optimum trap requires BROADER exploration to escape
- step_fraction=0.5 was too conservative - increasing to 1.0 for larger jumps
- ES needs to make bigger jumps to find better weight regions
- Current weights are trapped; need to explore distant regions
- Disabling grid_search saves time for ES to do its own exploration
- With step_fraction=1.0, ES will make larger proposals and potentially escape local optimum
- Need to monitor games_at_or_over_cap as primary metric (must reach 0)

## Plan for next iteration
- Increase step_fraction to 1.0 for broader exploration around current weights
- Disable grid_search to save time for ES exploration
- Reduce max_iterations to 20 to save time while we explore
- Keep sim_words at 1000 for reasonable verification before claiming success
- Keep rule_factor=5.0 for faster step growth when we succeed
- Monitor games_at_or_over_cap - need this to reach 0
- If ES still stagnates after 20 iterations:
  - Consider complete reset with different initial weights
  - Or try manual weight perturbation based on worst word analysis
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
