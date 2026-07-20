# Start here

1. Open this folder as a new Git repository in Codex.
2. Paste the following message into Codex:

```text
Read AGENTS.md and docs/CODEX_MASTER_PROMPT.md in full. Inspect every file under reference/. Then execute the master prompt end to end in this repository. Start by creating docs/EXEC_PLAN.md, but do not stop after planning. Implement, run tests, fix failures, and provide the required engineering handover only after the critical definition-of-done checks pass.
```

3. Do not place real secrets in source control. Codex should create `.env.example`; put the real FRED API key and deployment secrets only in the VPS `.env` file.
