---
name: project-orchestration
description: Follow the ResolveX AI architecture, phase gates, coding conventions, and contract-first implementation process. Use whenever implementing or refactoring project-wide components.
---
# Project Orchestration
- Read `PRD.md` and `ANTIGRAVITY_BUILD_PLAN.md` first.
- Implement one explicitly requested phase at a time.
- Preserve architecture boundaries: frontend, API, domain, providers, agents, graph, policies, and infrastructure.
- Add/update typed contracts and tests with every feature.
- Never mark a feature complete unless its acceptance criteria and smoke test pass.
- Keep simulation clearly labelled and never represent it as a live bank connection.
- Report files changed, commands run, test outcomes, limitations, and next gate.
