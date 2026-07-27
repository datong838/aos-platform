import { describe, expect, it } from "vitest";
import {
  CATEGORY_LABELS,
  batchAddTag,
  batchDeleteIds,
  batchMoveCategory,
  computeMediaStats,
  detectCategory,
  filterMedia,
  formatBytes,
  toggleTag,
  type MediaItem,
} from "./MediaSetsPage";

const MOCK_MEDIA: MediaItem[] = [
  { rid: "m1", name: "photo.jpg", category: "image", bytes: 2048576, contentType: "image/jpeg", tags: ["商品"], stored: true },
  { rid: "m2", name: "data.csv", category: "document", bytes: 1024, contentType: "text/csv", tags: ["demo"], stored: true },
  { rid: "m3", name: "video.mp4", category: "video", bytes: 52428800, contentType: "video/mp4", tags: ["教程"], stored: true },
  { rid: "m4", name: "audio.mp3", category: "audio", bytes: 51200, contentType: "audio/mpeg", tags: [], stored: false },
  { rid: "m5", name: "report.pdf", category: "document", bytes: 819200, contentType: "application/pdf", tags: ["报告", "Q2"], stored: true },
];

describe("MediaSetsPage · CATEGORY_LABELS", () => {
  it("图片", () => { expect(CATEGORY_LABELS.image).toBe("图片"); });
  it("文档", () => { expect(CATEGORY_LABELS.document).toBe("文档"); });
});

describe("MediaSetsPage · detectCategory", () => {
  it("image/jpeg → image", () => {
    expect(detectCategory("image/jpeg", "photo.jpg")).toBe("image");
  });
  it("video/mp4 → video", () => {
    expect(detectCategory("video/mp4", "clip.mp4")).toBe("video");
  });
  it("audio/mpeg → audio", () => {
    expect(detectCategory("audio/mpeg", "song.mp3")).toBe("audio");
  });
  it("application/pdf → document", () => {
    expect(detectCategory("application/pdf", "doc.pdf")).toBe("document");
  });
  it("text/csv → document", () => {
    expect(detectCategory("text/csv", "data.csv")).toBe("document");
  });
  it("空 contentType + png 扩展名 → image", () => {
    expect(detectCategory("", "pic.png")).toBe("image");
  });
  it("未知类型 → document (fallback)", () => {
    expect(detectCategory("application/octet-stream", "file.xyz")).toBe("document");
  });
});

describe("MediaSetsPage · formatBytes", () => {
  it("0 B", () => { expect(formatBytes(0)).toBe("0 B"); });
  it("KB", () => { expect(formatBytes(2048)).toBe("2.0 KB"); });
  it("MB", () => { expect(formatBytes(1048576)).toBe("1.0 MB"); });
  it("GB", () => { expect(formatBytes(1073741824)).toBe("1.0 GB"); });
  it("B 不显示小数", () => { expect(formatBytes(512)).toBe("512 B"); });
});

describe("MediaSetsPage · filterMedia", () => {
  it("空筛选返回全部", () => {
    expect(filterMedia(MOCK_MEDIA, "all", "").length).toBe(5);
  });
  it("按分类 image", () => {
    expect(filterMedia(MOCK_MEDIA, "image", "").length).toBe(1);
  });
  it("搜索名称", () => {
    expect(filterMedia(MOCK_MEDIA, "all", "photo").length).toBe(1);
  });
  it("搜索标签", () => {
    expect(filterMedia(MOCK_MEDIA, "all", "报告").length).toBe(1);
  });
  it("组合分类+搜索", () => {
    expect(filterMedia(MOCK_MEDIA, "document", "data").length).toBe(1);
  });
});

describe("MediaSetsPage · computeMediaStats", () => {
  it("total 正确", () => {
    expect(computeMediaStats(MOCK_MEDIA).total).toBe(5);
  });
  it("byCat.image 正确", () => {
    expect(computeMediaStats(MOCK_MEDIA).byCat.image).toBe(1);
  });
  it("byCat.document 正确", () => {
    expect(computeMediaStats(MOCK_MEDIA).byCat.document).toBe(2);
  });
  it("totalBytes 正确", () => {
    expect(computeMediaStats(MOCK_MEDIA).totalBytes).toBe(55348800);
  });
  it("空数组返回全 0", () => {
    const s = computeMediaStats([]);
    expect(s.total).toBe(0);
    expect(s.totalBytes).toBe(0);
  });
});

describe("MediaSetsPage · toggleTag", () => {
  it("添加新标签", () => {
    expect(toggleTag(["a"], "b")).toEqual(["a", "b"]);
  });
  it("移除已有标签", () => {
    expect(toggleTag(["a", "b"], "a")).toEqual(["b"]);
  });
  it("空数组添加", () => {
    expect(toggleTag([], "new")).toEqual(["new"]);
  });
});

describe("MediaSetsPage · batchDeleteIds", () => {
  it("过滤掉 selected", () => {
    const sel = new Set(["m1", "m3"]);
    const remaining = batchDeleteIds(MOCK_MEDIA, sel);
    expect(remaining.length).toBe(3);
    expect(remaining.every((m) => !sel.has(m.rid))).toBe(true);
  });
  it("空 selected 返回全部", () => {
    expect(batchDeleteIds(MOCK_MEDIA, new Set()).length).toBe(5);
  });
});

describe("MediaSetsPage · batchAddTag", () => {
  it("给选中项添加标签", () => {
    const sel = new Set(["m1", "m2"]);
    const result = batchAddTag(MOCK_MEDIA, sel, "batch");
    const m1 = result.find((m) => m.rid === "m1")!;
    expect(m1.tags).toContain("batch");
  });
  it("不重复添加已有标签", () => {
    const sel = new Set(["m1"]);
    const result = batchAddTag(MOCK_MEDIA, sel, "商品");
    const m1 = result.find((m) => m.rid === "m1")!;
    expect(m1.tags.filter((t) => t === "商品").length).toBe(1);
  });
  it("未选中项不变", () => {
    const sel = new Set(["m1"]);
    const result = batchAddTag(MOCK_MEDIA, sel, "x");
    const m2 = result.find((m) => m.rid === "m2")!;
    expect(m2.tags).not.toContain("x");
  });
});

describe("MediaSetsPage · batchMoveCategory", () => {
  it("移动选中项分类", () => {
    const sel = new Set(["m1", "m2"]);
    const result = batchMoveCategory(MOCK_MEDIA, sel, "audio");
    expect(result.find((m) => m.rid === "m1")!.category).toBe("audio");
    expect(result.find((m) => m.rid === "m2")!.category).toBe("audio");
  });
  it("未选中项不变", () => {
    const sel = new Set(["m1"]);
    const result = batchMoveCategory(MOCK_MEDIA, sel, "audio");
    expect(result.find((m) => m.rid === "m3")!.category).toBe("video");
  });
});
