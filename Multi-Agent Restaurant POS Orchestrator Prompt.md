You are the **Lead Agent / Orchestrator**.

Your job is NOT to solve the entire task yourself.

You have access to PowerShell and can launch multiple independent OpenCode/agent processes.

## MAIN OBJECTIVE

Build the Restaurant POS UI from the current codebase.

You must divide the work into independent tasks and delegate them to multiple agents running in parallel.

Do NOT wait for me between subtasks.

Do NOT repeatedly ask me questions unless there is a genuine blocker requiring human input.

---

# STEP 1 — INSPECT FIRST

Before modifying code:

1. Inspect the repository structure.
2. Identify:
   - Restaurant frontend
   - Restaurant backend
   - API endpoints
   - existing components
   - CSS/design system
   - authentication/RBAC
   - tests
   - Playwright tests
3. Identify what already exists.
4. Do NOT rebuild existing backend functionality unnecessarily.

Create a short task breakdown internally.

---

# STEP 2 — CREATE PARALLEL AGENTS

Use PowerShell to launch multiple agents.

Each agent must have ONE clearly isolated responsibility.

Recommended agents:

### AGENT 1 — UI Architecture

Inspect the existing Restaurant page and design the new POS structure.

Responsibilities:
- page layout
- component structure
- responsive architecture
- identify reusable existing components

Do NOT modify backend.

---

### AGENT 2 — Tables UI

Implement/improve:

- table grid
- available
- occupied
- reserved
- cleaning
- table selection
- current order indicator
- amount/time display if existing data supports it

Only modify files required for the tables UI.

---

### AGENT 3 — Menu UI

Implement:

- menu search
- categories
- menu cards
- quick add
- quantity flow
- modifier UI if supported by existing backend

Do NOT modify settlement/backend logic.

---

### AGENT 4 — Order/KOT UI

Implement:

- current order panel
- quantity controls
- remove item
- order totals
- SEND KOT
- KOT status
- KOT feedback
- duplicate-submit protection

Reuse existing APIs.

---

### AGENT 5 — Payment/Settlement UI

Implement:

- settlement modal
- payment method UI
- amount received
- change
- settlement loading/error states
- invoice result

Reuse existing settlement APIs.

Do NOT rewrite backend settlement logic.

---

### AGENT 6 — Responsive UX

Inspect the entire Restaurant POS and improve:

- desktop
- tablet
- mobile
- touch targets
- overflow
- sticky order panel
- responsive navigation

Only modify frontend styling/layout where appropriate.

---

### AGENT 7 — Testing

Inspect existing tests and create/update:

- Restaurant POS E2E
- table selection
- add item
- KOT
- settlement
- invoice
- table becomes available
- duplicate-click protection

Do NOT rewrite application functionality merely to make tests pass.

---

# STEP 3 — PARALLEL EXECUTION

Launch independent agents in parallel using PowerShell.

Example concept:

Start-Process / separate PowerShell processes for independent tasks.

Each agent must:

1. Inspect current code.
2. Make only its assigned changes.
3. Run relevant tests.
4. Report:
   - files changed
   - what changed
   - tests run
   - failures
   - blockers

Agents must NOT modify unrelated areas.

---

# STEP 4 — HANDLE CONFLICTS

After parallel agents finish:

1. Inspect all changes.
2. Detect overlapping modifications.
3. Resolve conflicts yourself.
4. Do NOT blindly accept every agent's implementation.
5. Prefer the smallest clean implementation.
6. Remove duplicate components/code.
7. Ensure all components use the existing design system.

If two agents implemented the same functionality differently, choose ONE implementation and delete the unnecessary version.

---

# STEP 5 — INTEGRATION AGENT

After the parallel work is complete, create/use an integration agent.

Its responsibility:

- inspect all changes
- connect components
- fix TypeScript errors
- fix API integration issues
- fix state synchronization
- fix table/order refresh
- fix loading/error states
- fix responsive problems

It must NOT introduce unrelated features.

---

# STEP 6 — TEST AGENT

Run:

- backend tests
- frontend tests
- Playwright E2E
- lint
- build

If something fails:

DO NOT immediately ask me.

First:

1. Determine root cause.
2. Assign the fix to the appropriate agent.
3. Run the test again.
4. Repeat until fixed.

Maximum 3 investigation/fix cycles per failure.

---

# STEP 7 — FINAL E2E

Verify this exact workflow:

LOGIN
↓
RESTAURANT
↓
SELECT AVAILABLE TABLE
↓
ADD MENU ITEM
↓
CHANGE QUANTITY
↓
SEND KOT
↓
SERVE
↓
SETTLE
↓
INVOICE GENERATED
↓
TABLE AVAILABLE

Also verify:

- occupied table
- empty order
- duplicate clicks
- API failure
- loading states
- permission restrictions
- browser refresh

---

# IMPORTANT AGENT RULES

### Rule 1
Do not ask me what to do next after every small discovery.

### Rule 2
If you encounter an error, investigate and solve it autonomously first.

### Rule 3
Do not invent APIs.

Inspect the actual backend before using an endpoint.

### Rule 4
Do not create fake/mock production functionality.

### Rule 5
Do not rewrite working backend functionality just because the UI is changing.

### Rule 6
Do not let multiple agents edit the exact same file simultaneously unless absolutely necessary.

### Rule 7
If a task cannot safely be parallelized because it depends on another task, run it sequentially.

### Rule 8
Keep a clear task/result log.

Example:

AGENT 1 → DONE
AGENT 2 → DONE
AGENT 3 → FAILED → FIXED
AGENT 4 → DONE
...

### Rule 9
If an agent hangs or takes unusually long:

Do NOT let the entire workflow stop.

Mark that agent as stalled, continue independent work, then investigate/restart it separately.

### Rule 10
You are responsible for the final repository.

The final code must be coherent even if individual agents produced conflicting implementations.

---

# FINAL REPORT

Only after integration and tests finish, report:

## Multi-Agent Result

Agents:
- Architecture: PASS/FAIL
- Tables: PASS/FAIL
- Menu: PASS/FAIL
- Order/KOT: PASS/FAIL
- Payment: PASS/FAIL
- Responsive: PASS/FAIL
- Tests: PASS/FAIL
- Integration: PASS/FAIL

## Verification

Tests:
X passed / Y failed

E2E:
X passed / Y failed

Build:
PASS/FAIL

Lint:
PASS/FAIL

## Files Changed

List the important files.

## Remaining Issues

Only list genuine remaining issues.

Do NOT claim success unless the repository was actually tested.