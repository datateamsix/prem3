# MTA Channel Grouping Governance

Users edit a structured `ChannelGroupingRuleSet`, not raw production SQL.

## Flow

1. Discover source/medium/campaign values  
2. Apply current rules → coverage / unmapped  
3. Edit structured rules (priority + patterns → `output_channel_id`)  
4. Validate every `output_channel_id` against the pinned Channel Registry  
5. Approve → compile immutable `channel_grouping_vN` from Jinja UDF assets  
6. Provision to bound `prem3_modeling`  
7. Fixture + discovered-value validation + read-back fingerprint  

## Immutability

After a UDF version powers a recorded run, never `CREATE OR REPLACE` that version. Changes create `vN+1`. Optional `channel_grouping_current` is convenience only — historical runs pin the versioned routine.

## AI Search

Registry V1 includes `ai_search`. The default UDF maps identifiable AI-native referrals (ChatGPT, Perplexity, Gemini, Copilot, Claude, You.com, Poe). Undistinguished AI-inside-search traffic may remain `search_organic`.
