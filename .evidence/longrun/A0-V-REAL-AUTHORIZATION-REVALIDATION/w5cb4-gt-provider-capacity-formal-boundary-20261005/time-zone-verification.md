# Private issuer UTC verification

Baseline: m1@ae7e1a00238c85eb3a55228ffbd5119af5d921af, authority AOS-001378.

Plans amended before implementation in source and formal-boundary Task evidence. Source issuer connection now sets transaction-local UTC; each private identity gate rejects time-zone drift. No migration, global setting, authoritative database, or execution grant changed.

Real SCRAM PostgreSQL RED: 2 failed, 49 deselected, 8.66s. Role default Asia/Shanghai leaked into the connection, and explicit drift did not raise the required identity rejection.

GREEN plus adjacent: formal-boundary PG, original Source Action PG, and Source contracts: 167 passed, 7 existing warnings, 111.00s. Fixtures retain isolated aos_test_* databases; temporary issuer role default restored in finally. Diff whitespace check passed.

Independent route_supervisor review: no major issue in the minimal UTC change. UTC does not establish compatibility for historical references produced under another timezone. Full publication/COMMIT/fresh consumer and business first chain remain unverified; no full Task Delivery.

Forward route review: prioritize complete nonexecuting Source issuance and consumption, then shared physical capacity ledger plus one Intent; helper/test counts are not business milestones. Publication time contract remains pending user choice.
