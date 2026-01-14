# Architecture & Technology Standards

## Global Tech Stack
The entire "Indian Aroma" project must be built using the following stack.

### Frontend
*   **Framework**: Next.js (Latest stable).
*   **Language**: TypeScript (Strict Mode).
*   **Styling**: Built-in CSS Modules or Tailwind (Ralph's choice for "Dynamic/Premium" feel).
*   **State Management**: React Context or efficient local state.

### Backend
*   **Runtime**: Node.js.
*   **Language**: TypeScript (Strict Mode).
*   **Framework**: Express, NestJS, or Fastify (Choose one standard and stick to it).
*   **Database**: (Implied: Ralph decides, likely SQLite/Postgres/JSON for MVP).

## Quality Standards (Backpressure)
1.  **Strict Typing**: No `any` types allowed unless absolutely necessary and commented. `tsc` must pass.
2.  **Testing**:
    *   **Unit Tests**: All business logic and API endpoints must have corresponding unit tests.
    *   **Framework**: Jest or Vitest.
3.  **Linting**: Code must be clean and lint-free.

## Implementation Guide
*   **Monorepo**: Prefer a monorepo structure (e.g., `apps/web`, `apps/api`) or a clear structure within `src/` separation.
*   **API Type Safety**: Shared types between Frontend and Backend are highly recommended.
