# Qiyuehui metadata maintenance preparation verification

Result: preparation/rehearsal complete; live name change and installation activation NOT performed. Source database remains READ ONLY.

Fresh source identity: original colima container/image/named volume, cluster7683855731447750695, aos_current_preview_20260927 at a0v_159. Current org-org has identifier-only name; original aos_meta has Qiyuehui company name. Zero Host/assignment/operation/binding checked.

Consistent pg_dump custom backup and no-role-password globals retained in private/ with directory0700/files0600, excluded from Git. Independently copied second dump has same SHA256/size. Source fingerprints before/after backup match. Backups are not deleted.

Independent same-image network-none cluster restore succeeds across626 ordinary application tables in all non-system schemas, with original row counts and sorted row fingerprints exactly matching source. Source column data was not committed to evidence; only hashes/counts. Initial target and failed globals suffix retained.

Failures diagnosed: original aos_app is bootstrap roleOID10; independent qyh bootstrap changes that identity and PostgreSQL rejects original self-grantor. r3 starts with original bootstrap aos_app, skips only its exact already-existing CREATE ROLE line, preserves ALTER/settings and all grantors. Original source-role flags/membership match after restore; password hashes deliberately excluded, authentication restoration NOT proven.

Database CONNECT ACL is not carried by the selected non-create restore flow. Source PUBLIC only has TEMP, while fresh target default has CONNECT/TEMP. Isolated target CONNECT was revoked to reproduce exact source rights. Database encoding/locale/owner/ACL and all role metadata/membership then match (ACL array ordering normalized only).

Schema dump raw hashes differ. All lines match except generated dump restriction keys and36 inline CHECK constraints with same AND leaves in different parenthesization. Parsed PostgreSQL syntax trees are equal after removal of locations and flattening adjacent AND while preserving leaf order. Parser version180004 is an offline grammar check, not proof of PG16 semantic resolution in all cases; actual current/source matching schema symbols and same-image restored PG are retained. No unknown schema difference ignored, all nonchanged definitions/ownership/object ACL SQL exact.

Rehearsal: wrong expected name affects zero rows; successful exact id/name/updated_at CAS rollback restores all626 table fingerprints. Isolated committed rename changes only public.meta_org; table row counts and625 other table fingerprints unchanged. Post-rehearsal full source fingerprint still matches initial source, original name remains org-org.

Proposal is proposed-name-update.sql, still NOT executed on formal source. The precise one-row update is isolated from any installation/binding/approval/budget or Provider operation. Row count arithmetic guard must reject zero rows under ON_ERROR_STOP; formal source identity and current timestamp must be rechecked at execution.

Formal gate remains: existing Goal explicitly requires current source read-only; live metadata UPDATE needs an explicit supported scoped maintenance authorization. API in-memory catalog refresh also needs the registered service recovery workflow; metadata change alone does not prove browser display. No source writes, production restart, external calls, oldRun replay, mall-source reads, push or backup/volume deletion.

Full native Main, eight-workbench activation, actual configuration/Host/Owner/approval-budget readiness and natural business chain remain unfinished.

Exact proposed SQL additionally passed isolated positive exactly-one-row COMMIT and negative division-by-zero abort; negative leaves all626 fingerprints unchanged. Final source full fingerprint remains unchanged. See proposal-test-result.json.
