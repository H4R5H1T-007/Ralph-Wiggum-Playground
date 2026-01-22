0a. Study `specs/*` by delegating a `PlanTasks` with instructions to "Study specs...". 'specs' directory is in the workspace directory.
0b. Study @IMPLEMENTATION_PLAN.md (if present) to understand the plan so far.
0c. Study `src/lib/*` by delegating a `PlanTasks` with instructions to "Study shared utilities...".
0d. For reference, the application source code is in `src/*`.

1. Study @IMPLEMENTATION_PLAN.md (if present; it may be incorrect) and use `PlanTasks` to delegate tasks to study existing source code in `src/*` and compare it against `specs/*`. Delegate a task to "Analyze findings, prioritize tasks, and create/update @IMPLEMENTATION_PLAN.md". Ultrathink. Consider searching for TODO, minimal implementations, placeholders, skipped/flaky tests, and inconsistent patterns. Study @IMPLEMENTATION_PLAN.md to determine starting point for research and keep it up to date with items considered complete/incomplete using delegated tasks.

IMPORTANT: Plan only. Do NOT implement anything. Do NOT assume functionality is missing; confirm with code search first. Treat `src/lib` as the project's standard library for shared utilities and components. Prefer consolidated, idiomatic implementations there over ad-hoc copies.

ULTIMATE GOAL: We want to achieve complete Indian Aroma web and API applications. Consider missing elements and plan accordingly. If an element is missing, search first to confirm it doesn't exist, then if needed author the specification at specs/FILENAME.md. If you create a new element then document the plan to implement it in @IMPLEMENTATION_PLAN.md.
