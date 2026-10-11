# Empty Workshop catalog installation diagnosis

Rules: AGENTS plan first, minimal changes and data protection; aos-engineering-delivery; reviewed231-3 and231-9; latest user tenant correction.

User problem: current org-org/dev-project has approved@3 installation, no active revision and no runtime binding. Current empty page only offers reread and cannot explain installation status.

Scope: four exact component/test files from Task plus this evidence directory. No backend/schema/current DB writes or runtime start.

Design: reuse useInstallations/useRuntimeInstallation and existing strict AssetControl client. Only mount diagnosis for an empty Workshop route. Read at most5 current-scope installation summaries; per row read current runtime state. Show Chinese installation status and verified not_prepared/no-binding facts. Do not infer matching module ownership from names, all installs are labeled current-workspace records. Link to existing /apollo/assets installation management, not a synthetic activation route. Error/forbidden/unknown must not become missing or ready.

Identity: key the diagnosis subtree by current org/project/subject/roles/authRevision. Existing catalog identity subscription rerenders Host; remount clears prior state and read-hook cleanup discards old promises. Protect initial key changes, failed reads and inconsistent runtime identity/version/etag. Only current nonstale reads are shown.

Tests RED before implementation: approved@3/no binding displays real status and manage link; list failure shows unknown rather than absent; late orgA response cannot appear after orgB switch; existing empty host links diagnosis but visible modules retain original path. Add denied and mismatched runtime variants where applicable.

Verification: dedicated component+Host tests, adjacent catalog/shell/asset-reader tests, TypeScript/build, isolated browser rendering if available. Browser mocks prove UI behavior only; current signed service/catalog remains unactivated and this change does not restore eight live entries. Current production stack is not restarted by this continuation task.

Exit: scoped code verified and committed with Delivery/context sync. Next formal recovery must close current signature/Host/Owner/configuration/approval budget gates through original runtime-apply/verify. LongGoal and complete native Main stay incomplete.

Navigation review: /apollo/assets opens the existing AssetBundles page, not a selected installation tab. The diagnostic explicitly instructs selecting Installation Management, and the link is labeled Open Asset Bundles. No unsupported deep-link query was invented.
