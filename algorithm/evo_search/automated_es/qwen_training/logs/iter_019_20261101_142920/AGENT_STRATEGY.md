# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES stuck since iteration 6 with 8-91 games at/over cap (words needing >6 guesses)
- Current weights [0.843, 0.658, 8.314] have very high w2 (8.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - no improvements found, candidates had 4.2-4.3 avg vs baseline 3.593
- step_fraction=0.35 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- ES is trapped in a local optimum and needs larger jumps to find better regions

## Current hypothesis
- Local optimum requires LARGER steps to escape, not smaller
- step_fraction=0.35 was too conservative - ES jumping too little to find improvements
- Need step_fraction=0.45 to make more aggressive explorations
- Higher rule_target (0.4) to trigger step growth more frequently when we succeed
- Higher rule_factor (3.0) for faster step adaptation when we finally succeed
- w2 (third letter weight) at 8.31 is likely the main problem - needs to be reduced
- ES needs to find direction that reduces games_at_or_over_cap first (this is lexically more important than average)

## Plan for next iteration
- Increase step_fraction to 0.45 for more aggressive, exploratory proposals
- Increase rule_target to 0.4 to trigger step growth more frequently
- Increase rule_factor to 3.0 for faster step adaptation when we succeed
- Keep max_iterations at 30 for sufficient exploration
- Keep sim_words at 1000 for reasonable verification
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If still stuck after 30 iterations:
  - Consider increasing step_fraction further to 0.55
  - Or try different seed to perturb search direction
  - Or consider grid_search=true with focused offsets around current weights
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
