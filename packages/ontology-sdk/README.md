# @aos/ontology-sdk

Thin TypeScript client for AOS Ontology + Draft APIs.

- **Only** talks to `aos-api` (`/v1/objects/*`, `/v1/aip/drafts`).
- Sends `Authorization` + `X-Org-Id` + `X-Project-Id`.
- Writes go through **Draft** — no direct production bypass.

```ts
import { createOntologyClient } from "@aos/ontology-sdk";

const client = createOntologyClient({
  baseUrl: "http://127.0.0.1:8080",
  token: accessToken,
  orgId: "dev-org",
  projectId: "dev-project",
});

const { items } = await client.listObjects("WorkOrder");
```

Scheme: `docs/palantier/20_tech/146-目标态收口与ontology-sdk方案.md`
