# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- ES stuck since iteration 6 with 8 games at/over cap (words needing >6 guesses)
- Current weights [0.843, 0.658, 8.314] have high w2 (8.31) - likely over-penalizing 3rd letter matches
- 8 problematic words include "acaja" - hard to solve words
- step_fraction=0.25 was too conservative - ES not exploring enough to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- Iteration 3 found improvement (3.512) but wasn't kept - ES needs to keep better candidates

## Current hypothesis
- Local optimum trap requires LARGER steps to escape, not smaller
- step_fraction=0.25 was too conservative - ES jumping too little to find improvements
- Need step_fraction=0.35 to make larger explorations
- Higher rule_target (0.3) to trigger step growth more frequently when we succeed
- Lower rule_factor (2.5) for more gradual step adaptation
- w2 (third letter weight) may need adjustment - currently too high
- ES needs to find direction that reduces games_at_or_over_cap first

## Plan for next iteration
- Increase step_fraction to 0.35 for larger, more exploratory proposals
- Increase rule_target to 0.3 to trigger step growth more frequently
- Decrease rule_factor to 2.5 for more gradual step adaptation
- Keep max_iterations at 30 for sufficient exploration
- Keep sim_words at 1000 for reasonable verification
- Monitor games_at_or_over_cap as primary metric (must reach 0)
- If still stuck after 30 iterations:
  - Consider increasing step_fraction further to 0.45
  - Or try different seed to perturb search direction
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
