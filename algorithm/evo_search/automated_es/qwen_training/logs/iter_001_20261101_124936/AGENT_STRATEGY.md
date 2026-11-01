# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Current weights (w0=-9.0, w1=-2.0, w2=0.0) already achieve 0 over_threshold games on 2000-word sample
- Best average is 2.125 guesses - room for improvement
- step_fraction = 0.98 was too aggressive (98% of weight norm = huge jumps)
- grid_search with 8 offsets (512 evaluations) is wasteful when we already have good results
- Need to verify zero failures on full 10589-word list before stopping

## Current hypothesis
- Reduce step_fraction to 0.1 for more stable, fine-grained exploration
- Reduce grid_search offsets to 4 values (16 evaluations) to save compute
- Increase rule_target to 0.5 since we're already at 100% success rate
- Keep sim_words=2000 for fast iterations while refining weights
- Once stable weights found, verify on full list before finalizing

## Plan for next iteration
- Run with reduced step_fraction to explore local improvements around current weights
- Monitor if we can reduce average from 2.125 to ~2.0 or lower
- If success rate stays at 100%, consider increasing sim_words to verify on larger sample
- Watch for any increase in over_threshold games - if they appear, increase fail_penalty or adjust weights
- Prepare to switch to full word list (sim_words=0) once we have stable, zero-failure weights
- If no improvement after 10-15 iterations, consider changing strategy (different weight space exploration)
