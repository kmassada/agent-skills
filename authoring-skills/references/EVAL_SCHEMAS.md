# Skill Evaluation Schemas Reference

This reference documents the canonical JSON schemas for skill evaluations,
compatible with both **Anthropic Claude `skill-creator`** and **Google
Antigravity (`agy`)** evaluation harnesses.

---

## 1. Test Suite Definition: `evals/evals.json`

Every skill that requires automated evaluation should store its test cases in
`evals/evals.json` at the skill root.

### Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SkillEvals",
  "type": "object",
  "required": ["skill_name", "evals"],
  "properties": {
    "skill_name": {
      "type": "string",
      "description": "Must exactly match the 'name' field in SKILL.md frontmatter."
    },
    "evals": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "prompt", "expected_output", "expectations"],
        "properties": {
          "id": {
            "type": "integer",
            "description": "Unique integer identifier (1, 2, 3...)."
          },
          "prompt": {
            "type": "string",
            "description": "The realistic task prompt given to the agent."
          },
          "expected_output": {
            "type": "string",
            "description": "Human-readable description of what a successful run looks like."
          },
          "files": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Optional relative paths to fixture files required for this task."
          },
          "expectations": {
            "type": "array",
            "items": { "type": "string" },
            "description": "List of verifiable, declarative natural-language assertions."
          },
          "expected_command_patterns": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Optional regex patterns expected in tool calls (for deterministic test runners)."
          },
          "forbidden_command_patterns": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Optional anti-pattern regexes that must NOT be executed."
          }
        }
      }
    }
  }
}
```

### Example `evals.json`

```json
{
  "skill_name": "controlling-tmux",
  "evals": [
    {
      "id": 1,
      "prompt": "Run pytest tests/test_api.py in pane %2",
      "expected_output": "Dispatches pytest tests/test_api.py to tmux pane %2 without executing it locally.",
      "files": [],
      "expectations": [
        "The command is sent to pane %2 using tmux send-keys with C-m",
        "pytest is NOT executed directly in the agent's own subshell",
        "The agent does NOT steal user focus with select-pane"
      ],
      "expected_command_patterns": [
        "tmux send-keys -t %2 ['\"]pytest tests/test_api\\.py['\"] C-m"
      ],
      "forbidden_command_patterns": ["^pytest tests/test_api\\.py"]
    }
  ]
}
```

---

## 2. Grader Output Schema: `grading.json`

When a grader agent or automated evaluator scores a test run, it produces
`grading.json`:

```json
{
  "expectations": [
    {
      "text": "The command is sent to pane %2 using tmux send-keys with C-m",
      "passed": true,
      "evidence": "Found in step 2: 'tmux send-keys -t %2 pytest tests/test_api.py C-m'"
    },
    {
      "text": "pytest is NOT executed directly in the agent's own subshell",
      "passed": true,
      "evidence": "No direct execution of pytest found in subshell tool calls."
    }
  ],
  "summary": {
    "passed": 2,
    "failed": 0,
    "total": 2,
    "pass_rate": 1.0
  },
  "execution_metrics": {
    "total_tool_calls": 3,
    "total_steps": 2,
    "errors_encountered": 0
  },
  "timing": {
    "total_duration_seconds": 4.2
  }
}
```

---

## 3. Comparative Benchmark Schema: `benchmark.json`

Used when comparing runs across configurations (`with_skill` vs `without_skill`
baseline):

```json
{
  "metadata": {
    "skill_name": "controlling-tmux",
    "timestamp": "2026-09-05T21:30:00Z",
    "evals_run": [1, 2, 3],
    "runs_per_configuration": 1
  },
  "run_summary": {
    "with_skill": {
      "pass_rate": { "mean": 1.0, "stddev": 0.0 },
      "time_seconds": { "mean": 6.2, "stddev": 0.5 }
    },
    "without_skill": {
      "pass_rate": { "mean": 0.3, "stddev": 0.1 },
      "time_seconds": { "mean": 4.1, "stddev": 0.8 }
    },
    "delta": {
      "pass_rate": "+0.70",
      "time_seconds": "+2.1"
    }
  }
}
```

---

## 4. Origin & Official Reference Sources

- **Anthropic Skill-Creator Specification:** Canonical schemas derive from
  Anthropic's `skill-creator/references/schemas.md`.
- **Antigravity Customizations Reference:** Discovery and progressive disclosure
  rules derive from `agy-customizations/docs/skills.md`.

---

## 5. Principles of Writing Skill Evaluations

When creating benchmark test cases in `evals.json`, follow these core principles
to guarantee high-signal, authentic evaluation:

### A. Tasks, Not Quizzes

Evals are task-oriented operational tests, not knowledge quizzes. Do not ask the
agent to explain how to do something or test trivia about tool syntax. Give the
agent an authentic goal that requires using the skill:

- [BAD] _"How do I view container logs in Kubernetes?"_
- [GOOD] _"The payment gateway pod in namespace prod is restarting. Diagnose
  the crash."_

### B. No Tool Names in Prompts

Never mention specific tool names, CLI commands, subcommands, or flags in the
prompt. The skill is designed to teach the agent which tools to use; the eval
verifies whether the agent learned that mapping:

- [BAD] _"Run kubectl logs -p payment-gateway -n prod."_
- [GOOD] _"Inspect recent crash logs for the payment gateway in namespace
  prod."_

### C. Assert Outcomes, Not Implementation Details

Expectations must test WHAT was achieved, not HOW. Do not penalize the agent for
choosing a different, valid approach or command order:

- [BAD] _"Agent executes `grep -i error /var/log/app.log`"_
- [GOOD] _"The root cause error message is identified in the diagnostic
  summary"_

### D. Verifiable, Atomic Expectations

Each expectation should be a single, declarative statement describing what must
be true in the final output or tool state. Keep assertions atomic so graders can
pinpoint exact regressions.
