# PostgreSQL Ed25519 verification dependency

Isolated prototype for the capacity Source SQL signature boundary. This directory
does not install into current databases or modify default deployment images.
The extension calls OpenSSL PureEdDSA one-shot verification, with no private key,
signing, table access, network, file access, or trust-policy decisions.

`aos_ed25519.verify(signature bytea, message bytea, public_key bytea)` returns
false for wrong lengths, invalid signatures or messages over 2MiB. `STRICT`
returns SQL NULL for a NULL argument. Business gates must require `IS TRUE`.
Logical TOAST sizes are checked before decompression. All PostgreSQL input
processing precedes EVP allocation; EVP objects are freed before further PG APIs.

Installation requires a controlled administrator. The schema and sole function
belong to fixed `aos_ed25519_owner`, NOLOGIN/NOINHERIT with no elevated flags or
memberships. Preexisting target ownership or explicit privileges are rejected.
PUBLIC has no schema/EXECUTE grants. No runtime or private issuer gets a grant.
Production integration requires separate image/binary provenance and exact
owner/ACL/catalog admission, as well as the existing migration/backup gates.

A matching signature is not a trusted Source. The publication command must
derive its key from current independently authorized root/permit records, verify
purpose, target, canonical bytes, approvals and deadlines, and protect those
facts through its original caller COMMIT. A requester-supplied key or this
function's true result alone grants no capacity, mapping, Start or Model execution.

Build the isolated Dockerfile with `PG_BASE_IMAGE` pinned to an inspected local
image identity; retain source, binary, dependency and image hashes with the
native SQL acceptance. No key management/TCE or general SQL signing is exposed.
