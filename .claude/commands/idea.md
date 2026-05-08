Append an insight entry to IDEAS.md at the project root (create the file if it doesn't exist).

Input: $ARGUMENTS

Rules:
- Entry format: `- [Lens] insight text (severity)`
  - Lens must be one of: Self, User, Code, Market
  - Severity must be one of: low, med, high
- If the input does NOT include a lens label in [brackets], STOP and ask which lens before appending. Do not guess.
- If the input does NOT include a severity, default to (med) without asking.
- Append the formatted entry as a new line under the `## Insights` section.
- If IDEAS.md doesn't exist, create it with an `## Insights` heading first, then append.
- Confirm the entry was written by echoing it back in one line.
