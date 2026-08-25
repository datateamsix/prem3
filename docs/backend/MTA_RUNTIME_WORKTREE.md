# M5-01 worktree — ownership boundaries

**Worktree:** `../prem3-m5-01`  
**Branch:** `feature/prem3-m5-01-mta-journey-attribution-runtime`  
**Base commit (M5-00):** `ecfb95d6d19720b30323dbed80bfd9f636c19302`

## Own (write)

- `app/modeling/mta/**`
- `app/workers/mta/**` (or canonical MTA worker location)
- `scripts/mta/**`
- `sql/mta/**` (if/when present)
- `tests/unit/test_mta_*` and `tests/unit/test_mmm_m5_*` as MTA runtime evolves
- `tests/integration/test_mta_*`
- `docs/backend/MTA_RUNTIME*`
- MTA-specific Dockerfile / worker build files only

## Read-only / no-touch (ADK/skills agent owns)

- `.agents/**`
- `skills/**` (repo root skill packs)
- `app/adk/**`
- `app/agents/**`
- ADK registry files
- shared skill registry implementation

## Contract rule

M5-00 already shipped skill/asset stubs under `app/modeling/mta/skills/` and `external_assets.py`.  
M5-01 **consumes** those contracts; do **not** evolve agent/skill implementation here.
