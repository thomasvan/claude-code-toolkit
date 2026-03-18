# Claude Code Toolkit

Agents, skills, hooks, and scripts for Claude Code. A collection of patterns built over a year of daily use that make Claude Code significantly more effective for real development work.

## What this is

A routing system that matches your requests to specialized domain agents, enforces workflow methodologies that prevent skipping steps, and accumulates knowledge across sessions so the system improves over time.

The core idea: instead of hoping Claude figures out the right approach, route to an agent that has deep domain expertise and pair it with a skill that enforces a methodology. `/do debug this Go test` doesn't just "debug." It routes to a Go specialist agent, loads Go-specific idioms, and enforces a REPRODUCE, ISOLATE, IDENTIFY, FIX workflow with gates between each phase.

This system is built around my work. The agents reflect my domains. The skills reflect my workflows. You'll get value from the patterns and infrastructure, but the real payoff comes from building your own agents and skills for your domains using these as reference.

## How to use this

**Study the patterns.** The most valuable thing here isn't the install script. It's the structure.

- **`agents/*.md`** Domain-expert system prompts with routing metadata, force-triggered skills, and phase gates. Pick one and read it. The pattern: frontmatter declares triggers and capabilities, the body is deep domain expertise, the end has a quality gate that prevents declaring victory without evidence.

- **`skills/*/SKILL.md`** Workflow methodologies that enforce process. The `systematic-debugging` skill has four phases (REPRODUCE, ISOLATE, IDENTIFY, FIX) with gates between them. You can't skip to "fix" because the skill checks. Steal this pattern for any multi-step workflow.

- **`hooks/*.py`** Event-driven automation. The `error-learner.py` hook watches for tool errors, stores error-to-solution patterns in SQLite, and suggests fixes when it sees similar errors later. The system learns from its own mistakes.

- **`skills/comprehensive-review/SKILL.md`** Multi-wave parallel dispatch. Wave 0 discovers packages, Wave 1 runs specialized reviewers in parallel, Wave 2 does cross-cutting analysis using Wave 1 findings. A template for "fan out, gather, synthesize."

- **`skills/do/SKILL.md`** A natural-language routing layer. You describe what you want, it classifies domain + action + complexity, selects the right agent and skill, and handles force-routing for specific triggers.

Read the patterns, then build your own agents for your domains, your own skills for your workflows, your own hooks for your pain points. The system includes tools to help: `/do create an agent for [your domain]` and `/do create a skill for [your workflow]` scaffold new components using the same patterns. The `.local/` overlay lets you add private agents and skills that survive updates.

**Or install it.** If you want to try the whole system:

```bash
git clone https://github.com/notque/claude-code-toolkit.git ~/claude-code-toolkit
cd ~/claude-code-toolkit

# See what would happen first
./install.sh --dry-run

# Install
./install.sh --symlink    # symlink mode (updates via git pull)
# OR
./install.sh --copy       # copy mode (stable, re-run to update)
```

The installer links or copies agents, skills, hooks, commands, and scripts into `~/.claude/`, installs Python dependencies, and configures hooks in `settings.json`. It has `--dry-run`, `--uninstall`, and asks before overwriting anything.

**Back up first** if you have existing Claude Code customizations. Symlink mode replaces directories.

**Updating:** `cd ~/claude-code-toolkit && git pull` (symlink mode updates automatically).

---

## The `/do` router

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

You don't need to know which agent or skill exists. Just say what you want. The router matches you to a domain expert with a methodology. That single change, routing to specialized agents instead of hoping the general model figures it out, is where most of the value comes from.

### Force-routing

Certain triggers always invoke specific skills:

| Trigger | Skill | Why |
|---------|-------|-----|
| goroutine, channel, sync.Mutex | `go-concurrency` | Generic concurrency advice is how you get data races |
| _test.go, t.Run, benchmark | `go-testing` | Test patterns need table-driven, t.Helper, race detection |
| error handling, fmt.Errorf | `go-error-handling` | Error wrapping chains have specific Go patterns |

Without force-routing, Claude gives you generic advice when you need specific patterns.

---

## Multi-wave code review

`/comprehensive-review` dispatches parallel specialist agents across 3 waves. Each wave's findings feed the next. The security reviewer finds a swallowed error. The concurrency reviewer reads that finding and realizes the swallowed error is on a concurrent path. That's how you find invisible race conditions that no single-pass review catches.

**Wave 0** auto-discovers packages, dispatches per-package language specialists

**Wave 1** parallel foundation reviewers (security, concurrency, silent failures, performance, dead code, type design, API contracts, code quality, language idioms, docs)

**Wave 2** cross-cutting analysis using Wave 1 findings (deep concurrency, config safety, observability, error messages, naming consistency)

Final output: unified BLOCK/FIX/APPROVE verdict with severity-ranked findings.

---

## Cross-session learning

Most AI coding sessions are stateless. This one accumulates knowledge.

```
Feature completed
  -> retro-pipeline extracts learnings
  -> Saved to retro/L2/
  -> Next session, injected automatically when keywords match
  -> Agent receives context from prior work before starting
```

The `error-learner` hook does this automatically for tool errors: records the pattern, suggests the fix next time, tracks whether the fix worked, adjusts confidence. It's a SQLite database with reinforcement learning characteristics.

---

## Voice system

Create AI writing profiles that match a specific person's style. Bring your own writing samples, the system extracts measurable patterns, validates generated content against those patterns, and flags AI tells. See [docs/VOICE-SYSTEM.md](docs/VOICE-SYSTEM.md).

No pre-built voices included. The infrastructure ships; your voice is yours to create.

---

## What's included

| Component | Description |
|-----------|-------------|
| Domain agents | Specialized experts for Go, Python, TypeScript, Kubernetes, databases, and more |
| Workflow skills | TDD, debugging, refactoring, code review, PR pipelines, content creation |
| Event hooks | Error learning, auto-planning, retro injection, context archiving |
| Review agents | Parallel specialist reviewers across security, concurrency, performance, and more |
| Pipeline generator | Say "I need a pipeline for X" and the system builds agents, skills, and routing for it |
| Voice system | Clone a writing style with deterministic validation |
| PR workflow | `/pr-sync` stages, commits, pushes, and creates PRs in one command |
| `.local/` overlay | Your private customizations that survive `git pull` |

---

## FAQ

**Q: How do I get started?**
A: Read the patterns first. Pick an agent or skill that's close to your domain and study how it's structured. Then either install the whole system or adapt the patterns to your own setup.

**Q: Can I use just parts of it?**
A: Yes. Delete what you don't want. The router adapts to what's available. Hooks can be individually disabled in settings.json.

**Q: How is this different from Superpowers?**
A: Different tools for different needs. Superpowers is a clean workflow system (brainstorm, plan, build, review, ship) that installs in one command and works on multiple platforms. This toolkit focuses on deep domain agents with high context, a router that matches you to the right specialist, multi-wave review, and a knowledge system that compounds over time. One is a workflow. This is an arsenal. They're not competing.

**Q: Will this slow down my sessions?**
A: Hooks add ~200ms at session start. After that, agents only load when invoked. The comprehensive review takes longer because you're running waves of parallel agents.

**Q: I only write Python. Why are there Go agents?**
A: They're markdown files doing nothing until invoked. The cost of having them is zero. The cost of needing one and not having it is a bad session.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
