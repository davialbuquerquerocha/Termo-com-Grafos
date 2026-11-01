```parameters
max_iterations = 10
patience = 5
step_fraction = 0.75
rule_window = 5
rule_target = 0.5
rule_factor = 5.0
min_step_fraction = 0.001
grid_search = true
grid_offsets = [-5, 0, 5]
seed = 100001
max_guesses = 6
fail_penalty = 5.0
parallel_workers = 17
sim_words = 1000
sim_seed = 100003
path_dataset_dir = dataset
path_termo_words = dataset/termo_palavras_aceitas.txt
path_accepted_words = dataset/palavras_aceitas500.txt
```

```strategy
# AGENT_STRATEGY.md - Qwen's plan book

## Learnings
- Stuck in local optimum since iteration 6 - 15 consecutive iterations with ZERO improvements
- Current weights [10.84, 0.66, 28.31] have extremely high w2 (28.31) - likely over-penalizing 3rd letter matches
- Last 5 ES proposals ALL FAILED - candidate grades 4.2-4.8 vs baseline 3.548
- step_fraction=0.6 was insufficient to escape local optimum
- 1/5th rule never triggered (0 successes) - step size stuck at initial value
- sim_words=1000 sample keeps passing locally but FAILS full list verification - sample is too easy
- The optimizer is trapped and needs aggressive exploration to escape

## Current hypothesis
- Local optimum requires MUCH larger steps to escape
- Current step_fraction=0.6 is too conservative - ES jumping too little
- w2 (third letter weight) at 28.31 is likely the main problem - needs to be reduced significantly
- ES needs to find direction that reduces games_at_or_over_cap first (lexically more important than average)
- Grid search should help jump to a different region of weight space
- Need to trigger the 1/5th rule to adapt step size dynamically
- Time budget is tight (57m28s used, ~1h30m remaining) - need to be efficient

## Plan for next iteration
- INCREASE step_fraction to 0.75 for much more aggressive, exploratory proposals
- REDUCE grid_search cost: use only 3 offsets [-5, 0, 5] instead of 5 (27 evaluations vs 125)
- REDUCE max_iterations to 10 to save time (we're stuck, need efficiency)
- Keep sim_words at 1000 for reasonable verification
- Keep fail_penalty at 5.0 since avoiding failures is priority
- Monitor games_at_or_over_cap as PRIMARY metric (must reach 0 for success)
- Monitor average guesses as SECONDARY metric
- If grid search doesn't help after 10 iterations:
  - Consider even larger step_fraction (0.80+)
  - Or try different seed to perturb search direction
  - Or consider reducing w2 more aggressively through grid search
- Once games_at_or_over_cap reaches 0 on 1000 words, run full 10589-word validation
- If improvement found, increase sim_words for full list verification
- If still stuck: consider that current weights might need a complete reset or different approach
```