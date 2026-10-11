# Tenant and Workshop visibility diagnosis

This delivery proves diagnosis only. Tenant restoration, activation and the natural business first chain remain incomplete.

Fresh READ ONLY observations:
- Current database aos_current_preview_20260927, cluster7683855731447750695, migration a0v_159. Org org-org and workspace dev-project have identifier-only display names.
- Original aos_meta still holds the Qiyuehui company display name for org-org and the default dev-project workspace. This does not prove completeness of all original business data.
- Current installation ccdcb0f0-1040-4bc6-aa0c-d045f5689813 has draft1/submitted2/approved3, activeRevision null. Host identities, assignments, runtime operations and bindings are all zero.
- workshop_catalog_source requires an active installation revision; RuntimeWorkshopCatalog additionally requires ready binding and matching route authority. The current installation cannot supply visible module entries. The frontend renders the empty catalog message shown by the user.
- Four relevant API source files exactly match the frozen running source hashes. This is not a whole-running-source/latest-HEAD claim.
- Context document227 records creating a new database rather than restoring old business records, approving the current installation, switching the preview service and leaving binding zero. Document238 records the rejected generic Apply and required runtime-apply/verify path. The missing activation predates this computer restart.

Reviewed Rules and plans: AGENTS, aos-engineering-delivery, 231-3 installation/runtime admission, 231-9 eight domain workbenches and tenant instance separation.

Recovery sequence and two registered safe candidates are in plan.md. Preserve real formal Host/Owner/configuration/budget approval gates. Do not UPDATE active pointers, forge bindings, create a substitute tenant or copy historical test installations.

No production code or database writes, Host/worker/Provider start, mall-source read, unknown request replay or push. Existing worktree modifications remain.

The first verification-document write failed due to stdin encoding, so staging and commit also failed because that file was absent. No commit or product effect occurred. This ASCII retry preserves the diagnostic content and records that failure.

ObservedAt: 2026-10-11T05:53:31.240021+00:00
Base HEAD: 87efd7c8125981149b0605003bf5f5341ba3e415
