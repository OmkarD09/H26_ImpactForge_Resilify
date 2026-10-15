# Agent Skills & Harness Configuration

This repository is equipped with agent skills, rules, and workflows from three primary frameworks:

1. **[Impeccable](https://github.com/pbakaus/impeccable)**
   - **Focus**: The design language and engine that elevates AI coding harnesses to professional design standards.
   - **Path**: `.agents/skills/impeccable/`
   - **Key Capabilities**: Design critique, type-setting, visual balance, color hierarchy, craft floor elevation, and polish.

2. **[Taste Skill](https://github.com/Leonxlnx/taste-skill)**
   - **Focus**: Anti-slop frontend art direction distilled from curated sites (Awwwards, One Page Love).
   - **Path**: `.agents/skills/taste-skill/` and companion skills (`brandkit`, `minimalist-skill`, `brutalist-skill`, `soft-skill`, `redesign-skill`, `stitch-skill`, `image-to-code-skill`, etc.)
   - **Key Capabilities**: Non-generic UI design, concept-driven styling, real-browser inspection, and visual refinement loops.

3. **[ECC (Everything Claude Code / Agent Harness)](https://github.com/affaan-m/ECC)**
   - **Focus**: Cross-harness agent performance optimization, testing, security, and full-stack software engineering standards.
   - **Paths**:
     - `.agents/skills/` (300+ domain skills)
     - `.agents/rules/` (coding, review, security standards)
     - `.agents/workflows/` (orchestration and delivery flows)
     - `.agents/agents/` (specialized sub-agent definitions)
   - **Key Capabilities**: TDD/E2E workflows, security reviews, architecture decision records, API design, and performance tuning.

## Discovery & Usage

All skills follow the standard `SKILL.md` format with YAML frontmatter and are located under `.agents/skills/`. They are automatically indexed and available to Google Antigravity, Claude Code, Cursor, Codex, and other compatible agent harnesses.
