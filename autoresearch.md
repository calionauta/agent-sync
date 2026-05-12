# Autoresearch Rules

This file governs the autoresearch loop.

## Loop Pattern
1. Read the project code and understand the benchmark
2. Form a hypothesis about what to change
3. Make the change
4. Run the benchmark via run_experiment
5. Log the result via log_experiment
6. Repeat

## Benchmark
The benchmark is whatever captures the user's issue — in this case, running `agent-sync push` and measuring whether it completes and how long it takes.

## Optimization Target
Primary metric: `exit_code` (0 = success, 1 = failure/hang)
Secondary metric: `duration_s` (how long it takes to complete)

## Rules
- Do not cheat on benchmarks
- Do not overfit
- Each experiment must test a real change
- If a change doesn't help, discard it
- Keep changes that improve the metric
