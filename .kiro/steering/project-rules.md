---
inclusion: always
---

# Project rules for this repo

- This is a Kiroween 2026 hackathon entry. Only code written after 30 Oct 2026 may be committed.
  Do not paste code from earlier projects. If a library or template is used, add it to the
  "Built during the hackathon" section of README.md with its source and license.
- Never commit secrets. Keys live in `.env` (gitignored); keep `.env.example` up to date.
- Never add `.kiro/` or any of its sub-folders to `.gitignore`.
- Every user-facing number (accuracy, latency, cost, counts) must come from a real run whose
  output file is committed. Do not type numbers by hand.
- The AI proposes, code verifies: anything the model produces that acts on the world or is shown
  as fact must pass a deterministic check first, and failures are logged and shown.
- Keep commits small, with plain messages that say what changed.
