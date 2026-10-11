# Qiyuehui organization name: formal maintenance preparation

Rules: AGENTS, aos-engineering-delivery,231-4 single PG authority/data preservation and231-3 unchanged installation gates.

Current source: colima-aos-extension/aos-a0v-recovery-pg, original named volume aos-a0v-recovery-pg-data, cluster7683855731447750695, database aos_current_preview_20260927 at a0v_159.

Proposed final write is limited to public.meta_org.name for id org-org, from identifier-only org-org to the existing original aos_meta company name. Exact original/current organization identity, expected timestamp and name CAS required. No workspace rename, membership, installation, active pointer, binding or runtime changes. Source remains read-only in this Task.

Steps before live maintenance: assert source identity/zero Host/assignment/operation/binding; take independent consistent custom pg_dump and no-role-password globals; SHA256/TOC/size and restrictive permissions; retain second checksum-verified backup copy; restore all globals/schema/data/ACL into a distinct same-image cluster with network none, no ports and independent tmpfs data. Do not attach source volume or run API/worker/Provider. Compare complete relation data and schema/owner/ACL surfaces where feasible before/after restoration. Rehearse exact one-row CAS rename, rollback and unexpected-current-name refusal; compare all other relation data unchanged and preserve installation/roles. Record gaps, do not replace failed restore with partial minimal tables.

Files: plan.md, collector/rehearsal script, restricted private backups excluded from Git, sanitized manifests/results and verification. D-wave formal-maintenance checklist separately registered. No product code changes.

Registered candidates: this exact maintenance-preparation Task can safely read source/restore independently; existing full native-ending Task is separately authorized but incomplete. Priority user-visible tenant recovery before more helper-only probes. Formal install/runtime configuration prerequisite gaps remain an independent task; no activation from name restoration.

Mutation intents recorded before isolated create/restore/update; unknown outcomes reconciled through read-only inspection before any retry. No deletion of any database, backup or volume. No push, no second writer.

Exit: full restore/rehearsal proof and concrete proposal ready for supported formal maintenance gate. This does not itself authorize live write or prove eight workbenches/first chain.
