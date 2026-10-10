# Exact PostgreSQL 16.14 callback source closure audit

Rules:231, complete native support contract and current unique-writer Lease; evidence-only audit, no runtime changes.

Fetch the official versioned PostgreSQL16.14 archive and published SHA256, verify before parsing. Retain archive uncommitted; extract only regular C/header files under src and contrib into this evidence directory. Inventory every RegisterXactCallback, RegisterSubXactCallback and unregister reference with exact file hash and enclosing function, then inspect initialization order relative to LOAD/session_preload/shared_preload and built-in registration. Catalog entries and preload settings are not complete loaded-backend evidence. Match source version to retained isolated PG16.14, but do not infer reproducible exact installed binary provenance from version alone.

Candidate1: source closure and registration lifecycle, authorized support read-only/evidence scope. Candidate2: Main full Receipt/precreation contract, requires complete Source/cert/all-eight-node validation and a proved final engine boundary. Choose candidate1 to determine whether a first-loaded extension can safely run after every existing callback without private state patches. No core binary patch, preload change, PG restart or runtime grant. Any incomplete provenance remains unproven rather than promoting the reader or test-only callback.
