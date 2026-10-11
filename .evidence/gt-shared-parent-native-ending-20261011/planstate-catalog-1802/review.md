# In-transaction function identity snapshot

Full fresh Source fixture passed155.35s. All197 observed OIDs resolve before cleanup and retain signature/owner/ACL/config/bodyhash/xmin. Independent XID66705 aborted, nine tables zero, no other clients, profile reset.

Readback r2 assumption of main-transaction-created missing functions failed: creation xid66703 committed. Three Source installation/consumer functions are absent after cleanup. r3 assumption that other194 bodies remain unchanged also failed: original fact/epoch-pair/evidence boundary body hashes changed. r4 records these differences without treating them as acceptance. Original cleanup explicitly drops consumer functions and runs legacy epoch profile restoration; exact restoration-body reconciliation remains required.

This preserves actual invocation identities, not full trusted closure/package lifecycle or business authority. No product or formal DB changes.
