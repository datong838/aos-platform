import { describe, expect, it } from "vitest";
import {
  computeDiff,
  summarizeDiff,
  diffLineTypeColor,
  diffLineTypeBg,
  diffLineTypeLabel,
  filterDiffLines,
  inlineDiff,
  MOCK_VERSION_CONTENTS,
  mapApiVersionsToContents,
  pickVersionContent,
  resolveDiffTexts,
  type DiffLine,
} from "./WikiDiffPage";

describe("WikiDiffPage · computeDiff", () => {
  it("returns all same lines for identical text", () => {
    const text = "line1\nline2\nline3";
    const diff = computeDiff(text, text);
    expect(diff.every((l) => l.type === "same")).toBe(true);
    expect(diff).toHaveLength(3);
  });

  it("detects added lines", () => {
    const old = "a\nb";
    const newText = "a\nb\nc";
    const diff = computeDiff(old, newText);
    const adds = diff.filter((l) => l.type === "add");
    expect(adds.length).toBeGreaterThanOrEqual(1);
    expect(adds.some((l) => l.rightContent === "c")).toBe(true);
  });

  it("detects deleted lines", () => {
    const old = "a\nb\nc";
    const newText = "a\nb";
    const diff = computeDiff(old, newText);
    const dels = diff.filter((l) => l.type === "del");
    expect(dels.some((l) => l.leftContent === "c")).toBe(true);
  });

  it("handles completely different text as add+del", () => {
    const diff = computeDiff("old_line", "new_line");
    expect(diff.some((l) => l.type === "add" || l.type === "del" || l.type === "mod")).toBe(true);
  });

  it("marks consecutive del+add as mod", () => {
    const old = "same\nold_line\nsame2";
    const newText = "same\nnew_line\nsame2";
    const diff = computeDiff(old, newText);
    const mods = diff.filter((l) => l.type === "mod");
    expect(mods.length).toBeGreaterThanOrEqual(1);
  });
});

describe("WikiDiffPage · summarizeDiff", () => {
  it("counts add, del, mod correctly", () => {
    const lines: DiffLine[] = [
      { type: "same", leftNum: 1, rightNum: 1 },
      { type: "add", leftNum: null, rightNum: 2 },
      { type: "del", leftNum: 2, rightNum: null },
      { type: "mod", leftNum: 3, rightNum: 3 },
      { type: "mod", leftNum: 3, rightNum: 3 },
    ];
    const s = summarizeDiff(lines);
    expect(s.added).toBe(1);
    expect(s.deleted).toBe(1);
    expect(s.modified).toBe(1);
    expect(s.total).toBe(3);
  });

  it("returns zeros for all-same", () => {
    const lines: DiffLine[] = [
      { type: "same", leftNum: 1, rightNum: 1 },
      { type: "same", leftNum: 2, rightNum: 2 },
    ];
    const s = summarizeDiff(lines);
    expect(s.added).toBe(0);
    expect(s.deleted).toBe(0);
    expect(s.modified).toBe(0);
  });
});

describe("WikiDiffPage · diffLineType helpers", () => {
  it("diffLineTypeColor returns color for each type", () => {
    expect(diffLineTypeColor("same")).toBeTruthy();
    expect(diffLineTypeColor("add")).toBeTruthy();
    expect(diffLineTypeColor("del")).toBeTruthy();
    expect(diffLineTypeColor("mod")).toBeTruthy();
  });

  it("diffLineTypeBg returns background for each type", () => {
    expect(diffLineTypeBg("add")).toContain("var");
    expect(diffLineTypeBg("del")).toContain("var");
  });

  it("diffLineTypeLabel returns prefix symbol", () => {
    expect(diffLineTypeLabel("same")).toBe(" ");
    expect(diffLineTypeLabel("add")).toBe("+");
    expect(diffLineTypeLabel("del")).toBe("-");
    expect(diffLineTypeLabel("mod")).toBe("~");
  });
});

describe("WikiDiffPage · filterDiffLines", () => {
  it("returns all when showSame=true", () => {
    const lines: DiffLine[] = [
      { type: "same", leftNum: 1, rightNum: 1 },
      { type: "add", leftNum: null, rightNum: 2 },
    ];
    expect(filterDiffLines(lines, true)).toHaveLength(2);
  });

  it("filters out same when showSame=false", () => {
    const lines: DiffLine[] = [
      { type: "same", leftNum: 1, rightNum: 1 },
      { type: "add", leftNum: null, rightNum: 2 },
    ];
    expect(filterDiffLines(lines, false)).toHaveLength(1);
  });
});

describe("WikiDiffPage · inlineDiff", () => {
  it("converts diff to inline format", () => {
    const lines: DiffLine[] = [
      { type: "same", leftNum: 1, rightNum: 1, leftContent: "a", rightContent: "a" },
      { type: "add", leftNum: null, rightNum: 2, rightContent: "b" },
      { type: "del", leftNum: 2, rightNum: null, leftContent: "c" },
    ];
    const inline = inlineDiff(lines);
    expect(inline).toHaveLength(3);
    expect(inline[0].type).toBe("same");
    expect(inline[1].type).toBe("add");
    expect(inline[2].type).toBe("del");
  });

  it("splits mod into del+add pair", () => {
    const lines: DiffLine[] = [
      { type: "mod", leftNum: 1, rightNum: 1, leftContent: "old", rightContent: "new" },
      { type: "mod", leftNum: 1, rightNum: 1, leftContent: "old", rightContent: "new" },
    ];
    const inline = inlineDiff(lines);
    expect(inline).toHaveLength(4);
    expect(inline[0].type).toBe("del");
    expect(inline[1].type).toBe("add");
    expect(inline[2].type).toBe("del");
    expect(inline[3].type).toBe("add");
  });
});

describe("WikiDiffPage · MOCK_VERSION_CONTENTS", () => {
  it("has at least 3 versions", () => {
    expect(MOCK_VERSION_CONTENTS.length).toBeGreaterThanOrEqual(3);
  });

  it("each version has content and metadata", () => {
    for (const v of MOCK_VERSION_CONTENTS) {
      expect(v.content).toBeTruthy();
      expect(v.author).toBeTruthy();
      expect(v.commitMessage).toBeTruthy();
    }
  });

  it("versions are in descending order", () => {
    for (let i = 0; i < MOCK_VERSION_CONTENTS.length - 1; i++) {
      expect(MOCK_VERSION_CONTENTS[i].version).toBeGreaterThan(MOCK_VERSION_CONTENTS[i + 1].version);
    }
  });
});

describe("WikiDiffPage · W3-C5 API / local fallback helpers", () => {
  it("mapApiVersionsToContents keeps content for local computeDiff", () => {
    const list = mapApiVersionsToContents([
      { version: 2, content: "b", author: "a", message: "m2", created_at: 2 },
      { version: 1, content: "a", author: "a", message: "m1", created_at: 1 },
    ]);
    expect(list[0].version).toBe(2);
    expect(list[0].content).toBe("b");
    expect(list[0].commitMessage).toBe("m2");
  });

  it("pickVersionContent falls back to first", () => {
    const v = pickVersionContent(MOCK_VERSION_CONTENTS, 999);
    expect(v.version).toBe(MOCK_VERSION_CONTENTS[0].version);
  });

  it("resolveDiffTexts prefers API full text when present", () => {
    const left = MOCK_VERSION_CONTENTS[1];
    const right = MOCK_VERSION_CONTENTS[0];
    const r = resolveDiffTexts(
      { from_version: 8, to_version: 9, from_content: "API-OLD", to_content: "API-NEW" },
      left,
      right,
    );
    expect(r.fromApi).toBe(true);
    expect(r.oldText).toBe("API-OLD");
    expect(r.newText).toBe("API-NEW");
  });

  it("resolveDiffTexts falls back to local version contents", () => {
    const left = MOCK_VERSION_CONTENTS[1];
    const right = MOCK_VERSION_CONTENTS[0];
    const r = resolveDiffTexts(null, left, right);
    expect(r.fromApi).toBe(false);
    expect(r.oldText).toBe(left.content);
    expect(r.newText).toBe(right.content);
  });

  it("local computeDiff still works on MOCK pair", () => {
    const left = MOCK_VERSION_CONTENTS.find((v) => v.version === 8)!;
    const right = MOCK_VERSION_CONTENTS.find((v) => v.version === 9)!;
    const diff = computeDiff(left.content, right.content);
    expect(diff.some((l) => l.type !== "same")).toBe(true);
  });
});
