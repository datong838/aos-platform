import { beforeEach, describe, expect, it } from "vitest";
import {
  clearWorkspaceLocalCache,
  MP_DRAFT_PREFIX,
  ONTOLOGY_KEYS,
} from "./workspaceCache";

describe("TWC.6 workspace cache clear", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("removes mp drafts and ontology keys, keeps api base", () => {
    sessionStorage.setItem(`${MP_DRAFT_PREFIX}p1`, "{}");
    sessionStorage.setItem("aos-tenant-v1", "{}");
    localStorage.setItem(ONTOLOGY_KEYS[0], "[]");
    localStorage.setItem("aos-api-base-v1", "http://127.0.0.1:8080");

    const r = clearWorkspaceLocalCache("test");
    expect(r.sessionRemoved).toBe(1);
    expect(r.localRemoved).toBe(1);
    expect(sessionStorage.getItem(`${MP_DRAFT_PREFIX}p1`)).toBeNull();
    expect(sessionStorage.getItem("aos-tenant-v1")).toBe("{}");
    expect(localStorage.getItem("aos-api-base-v1")).toBe("http://127.0.0.1:8080");
  });
});
