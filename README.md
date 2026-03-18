# Claude Code Toolkit

Agents, skills, hooks, and scripts for Claude Code. A collection of patterns built over a year of daily use that make Claude Code significantly more effective for real development work.

The core idea: instead of hoping Claude figures out the right approach, route to an agent that has deep domain expertise and pair it with a skill that enforces a methodology. `/do debug this Go test` doesn't just "debug." It routes to a Go specialist agent, loads Go-specific idioms, and enforces a REPRODUCE, ISOLATE, IDENTIFY, FIX workflow with gates between each phase.

This system is built around my work. The agents reflect my domains. The skills reflect my workflows. You'll get value from the patterns and infrastructure, but the real payoff comes from building your own agents and skills for your domains using these as reference.

---

## Install

```bash
git clone https://github.com/notque/claude-code-toolkit.git ~/claude-code-toolkit
cd ~/claude-code-toolkit

# See what would happen first
./install.sh --dry-run

# Install (pick one)
./install.sh --symlink    # symlink mode — updates via git pull
./install.sh --copy       # copy mode — stable, re-run to update
```

The installer links or copies agents, skills, hooks, commands, and scripts into `~/.claude/`. It verifies Python 3.10+, installs dependencies, and configures hooks in `settings.json`. It has `--dry-run`, `--uninstall`, and asks before overwriting anything.

**Back up first** if you have existing Claude Code customizations. Symlink mode replaces directories.

**Updating:** `cd ~/claude-code-toolkit && git pull` (symlink mode updates automatically).

**Partial use:** Delete what you don't want. The router adapts to what's available. Hooks can be individually disabled in `settings.json`.

---

## How to use it: the `/do` router

Everything goes through `/do`. That's the entry point.

```
You: "/do debug this Go test"

  Router classifies: domain=Go, action=debug
  Selects agent: golang-general-engineer
  Selects skill: systematic-debugging
  Force-routes: go-testing (trigger match)

  Agent loads Go-specific context and idioms
  Skill enforces: REPRODUCE -> ISOLATE -> IDENTIFY -> FIX -> VERIFY
  Scripts run deterministic validation (go vet, gopls, gofmt)
```

You don't need to know which agent or skill exists. Just say what you want. The router matches you to a domain expert with a methodology. That single change — routing to specialized agents instead of hoping the general model figures it out — is where most of the value comes from.

### Force-routing

Certain triggers always invoke specific skills:

| Trigger | Skill | Why |
|---------|-------|-----|
| goroutine, channel, sync.Mutex | `go-concurrency` | Generic concurrency advice is how you get data races |
| _test.go, t.Run, benchmark | `go-testing` | Test patterns need table-driven, t.Helper, race detection |
| error handling, fmt.Errorf | `go-error-handling` | Error wrapping chains have specific Go patterns |
| "create voice", "voice from samples" | `create-voice` | Voice calibration requires a specific multi-phase pipeline |
| "design feature", "plan feature" | `feature-design` / `feature-plan` | Feature lifecycle has explicit phases |

Without force-routing, Claude gives you generic advice when you need specific patterns.

### The architecture

```
Router → Agent → Skill → Script

1. Router (/do) classifies request, selects agent + skill
2. Agent (domain expert) executes with skill methodology
3. Skill (process) guides workflow with phase gates
4. Script (Python CLI) performs deterministic operations
```

LLMs orchestrate. Programs execute. When validation is needed, a script runs. When state must persist, a file is written.

---

## Features

### Multi-wave code review

`/comprehensive-review` dispatches parallel specialist agents across 3 waves. Each wave's findings feed the next. The security reviewer finds a swallowed error. The concurrency reviewer reads that finding and realizes the swallowed error is on a concurrent path. That's how you find invisible race conditions that no single-pass review catches.

**Wave 0** auto-discovers packages, dispatches per-package language specialists

**Wave 1** parallel foundation reviewers (security, concurrency, silent failures, performance, dead code, type design, API contracts, code quality, language idioms, docs)

**Wave 2** cross-cutting analysis using Wave 1 findings (deep concurrency, config safety, observability, error messages, naming consistency)

Final output: unified BLOCK/FIX/APPROVE verdict with severity-ranked findings.

### Retro knowledge system

Most AI coding sessions are stateless. This one accumulates knowledge across sessions.

```
Feature completed
  -> retro-pipeline extracts learnings (context + meta walkers in parallel)
  -> Knowledge organized in L1 (summary) / L2 (detailed) hierarchy
  -> Next session, relevant knowledge injected automatically by keyword match
  -> Agent receives context from prior work before starting
```

The retro system runs a 5-phase pipeline (WALK → MERGE → GATE → APPLY → REPORT) at feature lifecycle checkpoints. Two parallel walkers extract different kinds of knowledge:

- **Context walker**: domain and implementation learnings (what we learned about the problem)
- **Meta walker**: process learnings (how we worked, what caused friction)

Knowledge graduates upward (L3 → L2 → L1) as confidence grows. Mature patterns eventually get embedded directly into the agents that use them. The system improves from its own work.

### ADR system for multi-agent coordination

When creating new components (pipelines, agents, skills), the system uses Architecture Decision Records as the shared context for all agents involved.

```
/do create a pipeline for database migrations

  1. ADR written to adr/database-migrations.md
  2. ADR session registered (.adr-session.json)
  3. Every sub-agent automatically receives relevant ADR sections
     (skill-creator gets step-menu + type-matrix,
      agent-creator gets architecture-rules, etc.)
  4. Compliance checked after every component file is written
```

The `adr-context-injector` hook ensures every sub-agent spawned during creation tasks shares the same architectural decisions. The `adr-query.py` script provides role-targeted context extraction — each agent type gets only the ADR sections relevant to its role. This is how the system coordinates multi-agent creation without agents talking past each other.

### Voice cloning system

Create AI writing profiles that match a specific person's style. Bring your own writing samples, the system extracts measurable patterns, validates generated content against those patterns, and flags AI tells. See [docs/VOICE-SYSTEM.md](docs/VOICE-SYSTEM.md).

```
/create-voice              # Interactive: provide samples, get a voice profile
/do write in voice [name]  # Generate content matching the profile
```

The voice system uses deterministic Python scripts for validation — not self-assessment. `voice_analyzer.py` extracts metrics (sentence length distribution, comma density, contraction rate, fragment usage). `voice_validator.py` checks generated content against the profile and catches banned patterns. The wabi-sabi principle: natural imperfections are features, not bugs. Sterile grammatical perfection is an AI tell.

No pre-built voices included. The infrastructure ships; your voice is yours to create.

### Feature lifecycle

A structured pipeline for building features from design through release:

```
/feature-design     → Collaborative design, explore trade-offs, produce design doc
/feature-plan       → Break design into wave-ordered tasks with agent assignments
/feature-implement  → Execute plan by dispatching to domain agents
/feature-validate   → Run quality gates (tests, lint, type checks)
/feature-release    → Merge to main via PR, tag release, cleanup
```

Each phase produces artifacts. The retro pipeline runs at each checkpoint, extracting learnings that improve future features. The system learns from how you build, not just what you build.

### Pipeline generator

Say "I need a pipeline for X" and the system builds agents, skills, and routing for it.

```
/do create a pipeline for Prometheus monitoring

  1. Domain research discovers subdomains (metrics, alerting, dashboards, operations)
  2. Chain composer builds valid pipeline chains for each subdomain
  3. Scaffolder creates skills, agents, reference files, scripts
  4. Routing tables updated automatically
```

The pipeline generator uses a 7-phase flow: ADR → Domain Research → Chain Composition → Scaffold → Integrate → Test → Retro. It discovers subdomains rather than requiring you to specify them upfront.

### PR workflow

`/pr-sync` stages, commits, pushes, and creates PRs in one command. For personal repos, it runs up to 3 iterations of automated review-and-fix before creating the PR. For organization repos with CI gates, it pauses for confirmation at each step.

### Domain agents

56 specialized agents covering:

| Domain | Agents |
|--------|--------|
| Languages | Go, Python, TypeScript, Node.js |
| Infrastructure | Kubernetes/Helm, Ansible, Prometheus/Grafana, OpenSearch |
| Databases | PostgreSQL, SQLite/Peewee |
| Frontend | React, Next.js, UI/UX design, performance optimization |
| Review | 20 parallel specialist reviewers (security, concurrency, API contracts, etc.) |
| Process | Research coordination, project coordination, pipeline orchestration |
| Content | Technical documentation, technical journalism, voice system |
| Meta | Agent creator, skill creator, hook development, system upgrade |

### Workflow skills

95+ skills including:

- **Debugging**: `systematic-debugging` (REPRODUCE → ISOLATE → IDENTIFY → FIX)
- **Testing**: `test-driven-development`, `go-testing`, `testing-anti-patterns`
- **Review**: `comprehensive-review`, `go-code-review`, `parallel-code-review`
- **Quality**: `go-pr-quality-gate`, `python-quality-gate`, `universal-quality-gate`
- **Refactoring**: `systematic-refactoring` (characterize with tests first)
- **Content**: `blog-post-writer`, `voice-orchestrator`, `research-to-article`
- **Meta**: `skill-creation-pipeline`, `agent-upgrade`, `system-upgrade`

### `.local/` overlay

Your private customizations that survive `git pull`. Add local agents, skills, and hooks without modifying the toolkit itself.

---

## Studying the patterns

The most valuable thing here isn't the install script. It's the structure.

- **`agents/*.md`** — Domain-expert system prompts with routing metadata, force-triggered skills, and phase gates. Pick one and read it. The pattern: frontmatter declares triggers and capabilities, the body is deep domain expertise, the end has a quality gate that prevents declaring victory without evidence.

- **`skills/*/SKILL.md`** — Workflow methodologies that enforce process. The `systematic-debugging` skill has four phases (REPRODUCE, ISOLATE, IDENTIFY, FIX) with gates between them. You can't skip to "fix" because the skill checks. Steal this pattern for any multi-step workflow.

- **`hooks/*.py`** — Event-driven automation. Hooks fire on session start, prompt submission, tool use, and context compaction. They inject knowledge, detect complexity, enforce compliance, and capture learnings — all without LLM cost.

- **`skills/comprehensive-review/SKILL.md`** — Multi-wave parallel dispatch. Wave 0 discovers packages, Wave 1 runs specialized reviewers in parallel, Wave 2 does cross-cutting analysis using Wave 1 findings. A template for "fan out, gather, synthesize."

- **`skills/do/SKILL.md`** — A natural-language routing layer. You describe what you want, it classifies domain + action + complexity, selects the right agent and skill, and handles force-routing for specific triggers.

Read the patterns, then build your own agents for your domains, your own skills for your workflows, your own hooks for your pain points. The system includes tools to help: `/do create an agent for [your domain]` and `/do create a skill for [your workflow]` scaffold new components using the same patterns.

---

## FAQ

**Q: How do I get started?**
A: Install, then use `/do` for everything. It routes to the right agent and skill. Start with what you know — if you write Go, try `/do debug this test` or `/do review this PR`. The router handles the rest.

**Q: Can I use just parts of it?**
A: Yes. Delete what you don't want. The router adapts to what's available. Hooks can be individually disabled in `settings.json`.

**Q: How is this different from Superpowers?**
A: Different tools for different needs. Superpowers is a clean workflow system (brainstorm, plan, build, review, ship) that installs in one command and works on multiple platforms. This toolkit focuses on deep domain agents with high context, a router that matches you to the right specialist, multi-wave review, and a knowledge system that compounds over time. One is a workflow. This is an arsenal. They're not competing.

**Q: Will this slow down my sessions?**
A: Hooks add ~200ms at session start. After that, agents only load when invoked. The comprehensive review takes longer because you're running waves of parallel agents.

**Q: I only write Python. Why are there Go agents?**
A: They're markdown files doing nothing until invoked. The cost of having them is zero. The cost of needing one and not having it is a bad session.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
