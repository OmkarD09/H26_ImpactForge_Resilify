# Repository Skills Catalog

This directory contains agent skills imported from three upstream ecosystems to enhance design, frontend craft, architecture, and engineering workflows:

1. **[Impeccable](https://github.com/pbakaus/impeccable)** (`impeccable`)
   - Award-winning frontend design guidance, 24 specialized design commands (`polish`, `audit`, `critique`, `distill`, `animate`, `bolder`, `quieter`, `typeset`, `colorize`, etc.), live browser inspection, and anti-slop rules.
   - Primary entry point: [.agents/skills/impeccable/SKILL.md](file:///f:/H26_ImpactForge_Resilify/.agents/skills/impeccable/SKILL.md)

2. **[Taste Skill](https://github.com/Leonxlnx/taste-skill)** (14 skills)
   - Anti-slop frontend art direction, researched visual directions, real browser verification, and design enforcement.
   - Includes:
     - `taste-skill` (`design-taste-frontend`): v2 art direction from a study of 247 gallery sites.
     - `redesign-skill`: Audit and overhaul existing project UI/UX.
     - `soft-skill`: High-end, soft visual design with whitespace and spring motion.
     - `minimalist-skill`: Editorial, crisp monochrome/restrained UI.
     - `brutalist-skill`: Industrial brutalist design language with Swiss typography.
     - `stitch-skill`: Google Stitch-compatible semantic design rules.
     - `gpt-tasteskill`: Stricter variant for GPT and Codex models with GSAP motion direction.
     - `output-skill`: Anti-laziness enforcement (no placeholders, full complete code).
     - `image-to-code-skill`: Reference image analysis and code reproduction.
     - `imagegen-frontend-web`, `imagegen-frontend-mobile`, `brandkit`: Reference asset & concept generators.
     - `taste-skill-v1`, `taste-skill-v2-experimental`: Legacy and experimental versions.

3. **[ECC (Enterprise / Everything Claude Code)](https://github.com/affaan-m/ECC)** (311 skills)
   - Comprehensive suite covering fullstack, frontend, backend, database, testing, cloud infrastructure, security, performance, architecture, and developer operations.
   - Core categories:
     - **Frontend & UI**: `frontend-patterns`, `react-patterns`, `react-performance`, `react-testing`, `vue-patterns`, `nextjs-turbopack`, `frontend-a11y`, `motion-foundations`, `motion-advanced`, etc.
     - **Backend & APIs**: `fastapi-patterns`, `python-patterns`, `python-testing`, `golang-patterns`, `rust-patterns`, `nestjs-patterns`, `springboot-patterns`, etc.
     - **Databases & ORMs**: `postgres-patterns`, `mysql-patterns`, `redis-patterns`, `prisma-patterns`, etc.
     - **Security & Quality**: `security-review`, `security-scan`, `security-bounty-hunter`, `plankton-code-quality`, `tdd-workflow`, etc.
     - **Architecture & Planning**: `hexagonal-architecture`, `plan-canvas`, `plan-orchestrate`, `git-workflow`, etc.

## How Skills Are Used

The agent automatically discovers all skills in `.agents/skills/` through progressive disclosure. Only the skill name and description are held in memory until relevant, at which point the full instructions and tool procedures are loaded on demand.
