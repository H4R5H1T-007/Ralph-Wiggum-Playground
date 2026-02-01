0a. Study `specs/*` by delegating a `PlanTasks` with instructions to "Study specs...". 'specs' directory is in the workspace directory.
0b. Study @IMPLEMENTATION_PLAN.md (if present) to understand the plan so far.
0c. Study `src/lib/*` by delegating a `PlanTasks` with instructions to "Study shared utilities...".
0d. For reference, the application source code is in `src/*`.

1. Study @IMPLEMENTATION_PLAN.md (if present; it may be incorrect) and use `PlanTasks` to delegate tasks to study existing source code in `src/*` and compare it against `specs/*`. Delegate a task to "Analyze findings, prioritize tasks, and create/update @IMPLEMENTATION_PLAN.md". Ultrathink. Consider searching for TODO, minimal implementations, placeholders, skipped/flaky tests, and inconsistent patterns. Study @IMPLEMENTATION_PLAN.md to determine starting point for research and keep it up to date with items considered complete/incomplete using delegated tasks.

IMPORTANT: Plan only. Do NOT implement anything. Do NOT assume functionality is missing; confirm with code search first. Treat `src/lib` as the project's standard library for shared utilities and components. Prefer consolidated, idiomatic implementations there over ad-hoc copies.

RESEARCH: If you are unsure about the usage of a library (especially new versions like Prisma 7, Next.js 14+, etc.), DO NOT GUESS. Use `DelegateResearch` to look up the documentation via Context7.
- **Critical**: Use specific, technical queries.
- **Bad**: `query="how do I do the thing with the users"`
- **Good**: `query="prisma client create user example"` or `query="prisma schema datasource url"`
For example, `DelegateResearch(query="connection string format", library_name="prisma")`.

ULTIMATE GOAL: We want to achieve complete Indian Aroma web and API applications. Consider missing elements and plan accordingly.

## PLAN STRUCTURE
When creating or updating `@IMPLEMENTATION_PLAN.md`, you MUST follow this strict structure:
1. **Pending Tasks**: A prioritized list of atomic "units of work". Each item must be a single, completing task (e.g. "Create Login Page", "Fix Auth API").
2. **Completed Tasks**: History of done items.
3. **New Tasks**: Pending scope that was discovered but not yet prioritized.

**PROHIBITED SECTIONS**:
- NO "Overview"
- NO "Backpressure"
- NO "Context"
- NO "Architecture Diagrams"
**MOVE ALL CONTEXT/LEARNINGS TO `@AGENTS.md` (Long Term Memory).** The Plan is a Checklist, not a Wiki.

If an element is missing, search first to confirm it doesn't exist, then if needed author the specification at specs/FILENAME.md. If you create a new element then document the plan to implement it in @IMPLEMENTATION_PLAN.md.
