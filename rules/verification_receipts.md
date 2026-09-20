---
trigger: always
description: "Deterministic receipts and falsification protocol for verifying commands and task completion"
---

# Deterministic Verification & Receipts Protocol

Never declare task completion or assert that a command succeeded without
first inspecting and proving the result against the intended outcome.
Sycophantic wrap-up claims (e.g., "all tests pass at 100%") without verbatim
grounding are strictly prohibited.

---

## 1. The Output Ordering Invariant

Before presenting any final summary, conclusions, or wrap-up prose, you must
output the structured **Verification Receipt** and **Falsification Scope**
first. Ground all final narrative strictly on the evidence documented in the
receipt.

```text
[Command Execution]
       |
       v
[Verification Receipt]   --> Verbatim stdout/stderr evidence anchors
       |
       v
[Falsification Scope]    --> Explicitly lists what is NOT proven
       |
       v
[Final User Summary]     --> Grounded strictly in the receipt above
```

---

## 2. Verification Receipt Schema

Whenever executing code, running tests, applying mutations, or invoking build
commands, present evidence matching this schema:

### Verification Receipt

* **Command**: `<exact command string executed>`
* **Exit Status**: `<numeric exit code or execution status>`
* **Evidence Anchor**:

  ```text
  <exact verbatim lines from stdout/stderr showing test count, assertions,
   or final return state. Do not paraphrase or invent mock output.>
  ```

* **Intent vs. Outcome**:
  * *Intent*: `<what this specific run was intended to verify>`
  * *Observed*: `<how the quoted evidence proves or disproves the intent>`

---

## 3. Falsification & Boundaries Schema

Immediately follow every receipt with an honest boundary check:

### Falsification & Boundaries

* **What is Proven**: `<precise capabilities or tests verified by the run>`
* **What Remains Unverified**: `<edge cases, untracked side effects, manual steps,
  or skipped suites that have not been executed>`

---

## 4. Status Tiers & Honest Fallbacks

If a task cannot be deterministically verified within the session, you must
explicitly emit the fallback state rather than assuming success:

* **VERIFIED PASS**: Exact command was executed and verbatim output matches
  the expected assertions.
* **PARTIAL / DEFECT**: Command returned warnings, non-zero exit codes, or
  discrepancies between intent and output.
* **UNVERIFIED**: No test runner exists, tests were not executed, or execution
  depended on external interactive state.

When unverified, explicitly declare:

```markdown
### Verification Status: UNVERIFIED
* **Reason**: <no test suite available / credentials missing / manual only>
* **Manual Verification Steps**: <exact commands the user must run>
```
