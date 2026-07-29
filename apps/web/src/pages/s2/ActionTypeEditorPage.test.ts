import { describe, expect, it } from "vitest";
import {
  emptyForm,
  defaultPayloadFromParams,
  validateActionType,
  canTransitionTo,
  getSubmissionStep,
  stepIndex,
  isEditable,
  parseMarkings,
  summarizeParameters,
  deriveActionRid,
  parseJsonArraySafe,
  paramTypeBadge,
  ruleKindBadge,
  buildOverviewInputs,
  buildOverviewRules,
  ACTION_STATUS_LABELS,
  ACTION_STATUS_COLORS,
  SUBMISSION_STEPS,
  ACTION_NAV_SECTIONS,
} from "./ActionTypeEditorPage";

describe("ActionTypeEditorPage · emptyForm", () => {
  it("creates a form with default values", () => {
    const f = emptyForm();
    expect(f.id).toBe("");
    expect(f.name).toBe("");
    expect(f.objectType).toBe("WorkOrder");
    expect(f.status).toBe("draft");
    expect(f.parameters).toHaveLength(1);
  });

  it("accepts custom objectType", () => {
    const f = emptyForm("Patient");
    expect(f.objectType).toBe("Patient");
  });
});

describe("ActionTypeEditorPage · defaultPayloadFromParams", () => {
  it("builds payload with sample for required params", () => {
    const params = [
      { name: "reason", type: "string", required: true },
      { name: "note", type: "string", required: false },
    ];
    const payload = defaultPayloadFromParams(params);
    const parsed = JSON.parse(payload);
    expect(parsed.reason).toBe("sample");
    expect(parsed.note).toBe("");
  });

  it("adds default reason when no params", () => {
    const payload = defaultPayloadFromParams([]);
    const parsed = JSON.parse(payload);
    expect(parsed.reason).toBe("ok");
  });
});

describe("ActionTypeEditorPage · validateActionType", () => {
  it("passes for valid form", () => {
    const f = { ...emptyForm(), id: "close-order", name: "Close Order" };
    expect(validateActionType(f)).toHaveLength(0);
  });

  it("catches empty id", () => {
    const f = { ...emptyForm(), name: "Test" };
    expect(validateActionType(f)).toContain("id 不能为空");
  });

  it("catches empty name", () => {
    const f = { ...emptyForm(), id: "test-action" };
    expect(validateActionType(f)).toContain("name 不能为空");
  });

  it("catches invalid id format", () => {
    const f = { ...emptyForm(), id: "123 bad", name: "Test" };
    const errors = validateActionType(f);
    expect(errors.some((e) => e.includes("id 必须以字母"))).toBe(true);
  });

  it("catches empty objectType", () => {
    const f = { ...emptyForm(), id: "test", name: "Test", objectType: "" };
    expect(validateActionType(f)).toContain("objectType 不能为空");
  });

  it("catches duplicate param names", () => {
    const f = {
      ...emptyForm(),
      id: "test",
      name: "Test",
      parameters: [
        { name: "dup", required: true },
        { name: "dup", required: false },
      ],
    };
    expect(validateActionType(f)).toContain('parameter name "dup" 重复');
  });
});

describe("ActionTypeEditorPage · canTransitionTo", () => {
  it("allows draft → submitted", () => {
    expect(canTransitionTo("draft", "submitted")).toBe(true);
  });

  it("allows submitted → validated", () => {
    expect(canTransitionTo("submitted", "validated")).toBe(true);
  });

  it("allows validated → enabled", () => {
    expect(canTransitionTo("validated", "enabled")).toBe(true);
  });

  it("allows enabled → disabled", () => {
    expect(canTransitionTo("enabled", "disabled")).toBe(true);
  });

  it("allows submitted → draft (rollback)", () => {
    expect(canTransitionTo("submitted", "draft")).toBe(true);
  });

  it("disallows draft → enabled (must go through submit/validate)", () => {
    expect(canTransitionTo("draft", "enabled")).toBe(false);
  });

  it("disallows validated → draft (skip steps)", () => {
    expect(canTransitionTo("validated", "draft")).toBe(false);
  });
});

describe("ActionTypeEditorPage · getSubmissionStep", () => {
  it("returns editing for draft", () => {
    expect(getSubmissionStep("draft")).toBe("editing");
  });

  it("returns submitted for submitted", () => {
    expect(getSubmissionStep("submitted")).toBe("submitted");
  });

  it("returns validated for validated", () => {
    expect(getSubmissionStep("validated")).toBe("validated");
  });

  it("returns enabled for enabled", () => {
    expect(getSubmissionStep("enabled")).toBe("enabled");
  });
});

describe("ActionTypeEditorPage · stepIndex", () => {
  it("returns correct indices", () => {
    expect(stepIndex("editing")).toBe(0);
    expect(stepIndex("submitted")).toBe(1);
    expect(stepIndex("validated")).toBe(2);
    expect(stepIndex("enabled")).toBe(3);
  });
});

describe("ActionTypeEditorPage · isEditable", () => {
  it("returns true for draft", () => {
    expect(isEditable("draft")).toBe(true);
  });

  it("returns true for disabled", () => {
    expect(isEditable("disabled")).toBe(true);
  });

  it("returns false for submitted/validated/enabled", () => {
    expect(isEditable("submitted")).toBe(false);
    expect(isEditable("validated")).toBe(false);
    expect(isEditable("enabled")).toBe(false);
  });
});

describe("ActionTypeEditorPage · parseMarkings", () => {
  it("splits comma-separated values", () => {
    expect(parseMarkings("public, internal")).toEqual(["public", "internal"]);
  });

  it("handles Chinese comma", () => {
    expect(parseMarkings("公开，内部")).toEqual(["公开", "内部"]);
  });

  it("handles spaces", () => {
    expect(parseMarkings("a b c")).toEqual(["a", "b", "c"]);
  });

  it("filters empty strings", () => {
    expect(parseMarkings("a, , b")).toEqual(["a", "b"]);
  });

  it("returns empty for empty input", () => {
    expect(parseMarkings("")).toEqual([]);
  });
});

describe("ActionTypeEditorPage · summarizeParameters", () => {
  it("counts total, required, optional", () => {
    const params = [
      { name: "a", required: true },
      { name: "b", required: false },
      { name: "c", required: true },
    ];
    const s = summarizeParameters(params);
    expect(s.total).toBe(3);
    expect(s.required).toBe(2);
    expect(s.optional).toBe(1);
  });

  it("handles empty params", () => {
    const s = summarizeParameters([]);
    expect(s.total).toBe(0);
  });
});

describe("ActionTypeEditorPage · constants", () => {
  it("ACTION_STATUS_LABELS has 5 statuses", () => {
    expect(Object.keys(ACTION_STATUS_LABELS)).toHaveLength(5);
  });

  it("ACTION_STATUS_COLORS has 5 statuses", () => {
    expect(Object.keys(ACTION_STATUS_COLORS)).toHaveLength(5);
  });

  it("SUBMISSION_STEPS has 4 steps", () => {
    expect(SUBMISSION_STEPS).toHaveLength(4);
  });

  it("ACTION_NAV_SECTIONS has 8 sections", () => {
    expect(ACTION_NAV_SECTIONS).toHaveLength(8);
  });
});

describe("ActionTypeEditorPage · W4-C8b overview helpers", () => {
  it("deriveActionRid builds Foundry-like rid", () => {
    expect(deriveActionRid("EscalateCare")).toBe("ri.actions.main.action-type.EscalateCare");
    expect(deriveActionRid("")).toBe("ri.actions.main.action-type.unknown");
  });

  it("parseJsonArraySafe falls back on invalid JSON", () => {
    expect(parseJsonArraySafe("not-json", [{ name: "a" }])).toEqual([{ name: "a" }]);
    expect(parseJsonArraySafe('{"a":1}', [{ name: "a" }])).toEqual([{ name: "a" }]);
    expect(parseJsonArraySafe('[{"name":"x"}]', [])).toEqual([{ name: "x" }]);
  });

  it("paramTypeBadge defaults to string", () => {
    expect(paramTypeBadge()).toBe("string");
    expect(paramTypeBadge("Integer")).toBe("integer");
  });

  it("ruleKindBadge maps ops to Create/Modify/Delete/Link/Action", () => {
    expect(ruleKindBadge("create")).toBe("Create");
    expect(ruleKindBadge("required")).toBe("Modify");
    expect(ruleKindBadge("delete")).toBe("Delete");
    expect(ruleKindBadge("link")).toBe("Link");
    expect(ruleKindBadge("weird")).toBe("Action");
  });

  it("buildOverviewInputs skips empty names and marks required", () => {
    const items = buildOverviewInputs([
      { name: "reason", type: "string", required: true },
      { name: "  ", type: "string" },
      { name: "note", required: false },
    ]);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({ name: "reason", type: "string", required: true });
    expect(items[1].required).toBe(false);
  });

  it("buildOverviewRules prefers remote rules over criteria", () => {
    const remote = buildOverviewRules([{ field: "a", op: "required" }], "Patient", [
      { id: "r1", name: "Modify Patient", kind: "modify", target_otd_id: "Patient", condition: "status != closed" },
    ]);
    expect(remote).toHaveLength(1);
    expect(remote[0].kind).toBe("Modify");
    expect(remote[0].source).toBe("remote");
    expect(remote[0].summary).toContain("status");
  });

  it("buildOverviewRules derives from criteria when remote empty", () => {
    const derived = buildOverviewRules([{ field: "reason", op: "required" }], "WorkOrder", []);
    expect(derived).toHaveLength(1);
    expect(derived[0].source).toBe("criteria");
    expect(derived[0].kind).toBe("Modify");
    expect(derived[0].targetOt).toBe("WorkOrder");
  });
});
