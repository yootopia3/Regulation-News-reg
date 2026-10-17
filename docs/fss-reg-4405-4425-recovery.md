# FSS_REG 4405 / 4425 body recovery

Only FSS_REG regulation notices use the six-field `.krds-reg.reg2` form.
The title is its first `dd.form-conts`; two download anchors live outside
the form in `.attach-file-box`. Ordinary source collection and automatic
FSC/FSS/KFB retry limits are unchanged.

## Verification evidence

Both official pages were fetched once with unauthenticated GET on 2026-10-17:
https://github.com/yootopia3/Regulation-News-reg/actions/runs/39010725121/job/117332516833

The regression fixtures preserve the relevant six-field form and two original
attachment anchors, with whitespace normalized. They do not include the rest
of the page, navigation, or scripts.

Production read-only check found exactly one existing row for each notice,
both with content length zero:
https://github.com/yootopia3/Regulation-News-reg/actions/runs/39010926011/job/117333098817

## Exact-target repair

Run the workflow `repair_fss_reg.yml` on main with `apply=false` for inspection,
or `apply=true` to fill only missing bodies of 4405 and 4425. The script reads
both targets before any write, validates URL identity, refuses missing or
ambiguous rows, and never inserts. Each PATCH changes only content and checks
the row ID, agency, link and exact original empty value. It preserves any
concurrently filled body, rereads the row, and verifies the stored body and
selected unchanged metadata/analysis. It logs only target IDs, existence,
lengths and outcomes. No AI client, general collector or other-source repair
runs. The two updates are not a transaction; a partial completion is safe
to inspect and resume because nonempty bodies are skipped.

No credentials, stored bodies, or analysis results are included in logs or
artifacts. Use the existing production Actions secrets; no new permissions.

For this deployment, use a merge message containing `[skip actions]` to avoid
the ordinary collector push trigger and its unrelated paid analysis. Verify
Vercel's deployment and manually dispatch only this targeted repair workflow.
The pull request's exact-head CI must pass before merge. Normal scheduled
collection remains unchanged. Operational completion requires reading the
repair output; CI alone does not prove production persistence.
