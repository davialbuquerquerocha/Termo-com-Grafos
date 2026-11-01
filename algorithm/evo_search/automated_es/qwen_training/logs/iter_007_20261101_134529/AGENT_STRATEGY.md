# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Current weights [-1.96, -1.27, 11.50] have 91 games at or over cap on 2000-word sample
- ES has been stuck for 4+ iterations with no improvement (iter 2-4 same best_grade)
- step_fraction=0.25 was insufficient to escape local optimum around iteration 2
- Iteration 5 claimed success on 500 words but FAILED verification - sample too easy
- The 1/5th rule should adapt step size, but we need more exploration to find better weights
- Need to prioritize reducing games_at_or_over_cap (currently 91) before average

## Current hypothesis
- Local optimum at [-1.96, -1.27, 11.50] requires larger exploration steps
- 0.35 step_fraction (up from 0.25) should provide enough exploration to escape
- 2000-word sample is necessary for reliable metrics before full validation
- Reducing patience to 1 prevents wasting time on non-improving runs
- The weight space needs more aggressive perturbation to find better configurations

## Plan for next iteration
- Run ES with step_fraction=0.35 to escape local minimum
- Use 2000-word sample for consistent metrics (same sim_seed for comparability)
- Reduce patience to 1 to avoid wasting iterations on stagnation
- Monitor games_at_or_over_cap as primary metric (need this to reach 0)
- If stuck after 10 iterations, consider:
  - Further increasing step_fraction to 0.40
  - Testing different sim_seed for new random sample
  - Temporarily increasing fail_penalty to 7.0 to prioritize failure elimination
- Once games_at_or_over_cap reaches 0 on 2000+ words, run full 10589-word validation
- Keep fail_penalty=5.0 to balance average vs failure minimization
- If ES continues to stagnate, consider manual weight perturbation or reset
