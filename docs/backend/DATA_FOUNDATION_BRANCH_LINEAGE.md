# Data Foundation + Business IQ — branch lineage

**Design freeze:** `foundational-intake-freeze-2026-08-22-v1`  
**Working branch:** `feature/prem3-data-foundation-backend`  
**Recorded:** 2026-08-22

## Ancestry after restack

```text
origin_main_at_mission_start = dce8a209bb67fbaa3c8a78ae4e8a7384897252ed
dependency_base_sha          = 02cec50b6da6507838081e65086eaaf29a4a5329
dependency                   = Mission 2 / Mission 11 backend line
dependency_landed_on_main    = e7ec5fae802b49b61e5e1b5b3bfb073b4a511cb0  (PR #14)
branch_repair_required       = no
restack_completed            = yes
```

Mission 2 / Mission 11 landed on `main` via https://github.com/datateamsix/prem3/pull/14 (merge commit `e7ec5fa`). This freeze was then rebased onto `origin/main`. The resulting `origin/main...HEAD` diff is Business IQ + Data Foundation only.

## Freeze checkpoint

```text
FOUNDATIONAL_INTAKE_BACKEND_FREEZE
foundational-intake-freeze-2026-08-22-v1
original_checkpoint_sha      = a7a83b50f45d387f8ba16865b6b528f991a5d56f
restacked_feat_sha           = 2a0511308a4d5436ac8ce1aa5c58159434d20754
```

The original checkpoint SHA is the pre-restack freeze commit. Rebase rewrote that commit onto updated `main`; content is the same freeze, new SHA. No new foundational-intake capability was added.

## What not to do

- Do not rewrite qualified Mission 2 HEADs.
- Do not add foundational-intake capability on this branch after freeze.
