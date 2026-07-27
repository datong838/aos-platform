import { describe, expect, it } from "vitest";
import {
  columnToNumbers,
  extractColumns,
  extractTable,
  extractWhere,
  filterRows,
  formatSql,
  hasLimit,
  isSelectQuery,
  linePath,
  normalizeBars,
  paginate,
  parseCoords,
  projectToMap,
  rowsToMarkers,
  sortRows,
  toPieSlices,
  totalPages,
  type QueryResult,
  type ResultRow,
} from "./AipAnalystPage";

/* ----------------------------------------------------------------------------
 * SQL 解析纯函数
 * ------------------------------------------------------------------------- */
describe("AipAnalystPage · extractColumns", () => {
  it("提取多列", () => {
    expect(extractColumns("SELECT name, coords, rating FROM shops")).toEqual(["name", "coords", "rating"]);
  });

  it("SELECT * 返回 ['*']", () => {
    expect(extractColumns("SELECT * FROM shops")).toEqual(["*"]);
  });

  it("无 FROM 返回空", () => {
    expect(extractColumns("SELECT 1")).toEqual([]);
  });

  it("带 AS 别名提取别名", () => {
    const cols = extractColumns("SELECT t.name AS n, t.age AS a FROM users t");
    expect(cols).toEqual(["n", "a"]);
  });
});

describe("AipAnalystPage · extractTable", () => {
  it("提取表名", () => {
    expect(extractTable("SELECT * FROM shops WHERE 1=1")).toBe("shops");
  });

  it("支持 schema.table", () => {
    expect(extractTable("SELECT * FROM public.users")).toBe("public.users");
  });

  it("无 FROM 返回空字符串", () => {
    expect(extractTable("SELECT 1")).toBe("");
  });
});

describe("AipAnalystPage · extractWhere", () => {
  it("提取 where 条件", () => {
    expect(extractWhere("SELECT * FROM shops WHERE city = 'Northampton'")).toBe("city = 'Northampton'");
  });

  it("到 ORDER BY 为止", () => {
    const w = extractWhere("SELECT * FROM t WHERE x > 1 ORDER BY x");
    expect(w).toBe("x > 1");
  });

  it("无 where 返回空", () => {
    expect(extractWhere("SELECT * FROM t")).toBe("");
  });
});

describe("AipAnalystPage · hasLimit", () => {
  it("有 LIMIT 返回 true", () => {
    expect(hasLimit("SELECT * FROM t LIMIT 10")).toBe(true);
    expect(hasLimit("SELECT * FROM t limit 5")).toBe(true);
  });

  it("无 LIMIT 返回 false", () => {
    expect(hasLimit("SELECT * FROM t")).toBe(false);
  });
});

describe("AipAnalystPage · isSelectQuery", () => {
  it("SELECT 开头返回 true", () => {
    expect(isSelectQuery("SELECT * FROM t")).toBe(true);
    expect(isSelectQuery("  select 1")).toBe(true);
  });

  it("非 SELECT 返回 false", () => {
    expect(isSelectQuery("DELETE FROM t")).toBe(false);
    expect(isSelectQuery("UPDATE t SET x=1")).toBe(false);
    expect(isSelectQuery("INSERT INTO t VALUES (1)")).toBe(false);
  });
});

describe("AipAnalystPage · formatSql", () => {
  it("关键字大写", () => {
    const out = formatSql("select name from shops where x = 1");
    expect(out).toContain("SELECT");
    expect(out).toContain("FROM");
    expect(out).toContain("WHERE");
  });

  it("结尾加分号", () => {
    expect(formatSql("SELECT 1").endsWith(";")).toBe(true);
  });

  it("合并多余空格", () => {
    const out = formatSql("SELECT   name\n\nFROM   t");
    expect(out).not.toContain("  ");
  });
});

/* ----------------------------------------------------------------------------
 * 图表数据转换纯函数
 * ------------------------------------------------------------------------- */
describe("AipAnalystPage · columnToNumbers", () => {
  const rows: ResultRow[] = [
    { name: "a", rating: 5 },
    { name: "b", rating: 3 },
    { name: "c", rating: 4 },
  ];

  it("提取某列数值", () => {
    expect(columnToNumbers(rows, "rating")).toEqual([5, 3, 4]);
  });

  it("列不存在时填 0（NaN 被兜底为 0）", () => {
    expect(columnToNumbers(rows, "missing")).toEqual([0, 0, 0]);
  });
});

describe("AipAnalystPage · normalizeBars", () => {
  it("最大值归一化到 100", () => {
    const r = normalizeBars([10, 20, 5]);
    expect(r[1]).toBeCloseTo(100);
    expect(r[0]).toBeCloseTo(50);
    expect(r[2]).toBeCloseTo(25);
  });

  it("空数组返回空", () => {
    expect(normalizeBars([])).toEqual([]);
  });

  it("全 0 返回全 0", () => {
    expect(normalizeBars([0, 0])).toEqual([0, 0]);
  });
});

describe("AipAnalystPage · linePath", () => {
  it("生成 SVG path", () => {
    const p = linePath([1, 2, 3], 100, 50);
    expect(p.startsWith("M")).toBe(true);
    expect(p).toContain("L");
  });

  it("空数组返回空字符串", () => {
    expect(linePath([])).toBe("");
  });

  it("单值生成 M 指令", () => {
    const p = linePath([5]);
    expect(p.startsWith("M")).toBe(true);
    expect(p).not.toContain("L");
  });
});

describe("AipAnalystPage · toPieSlices", () => {
  it("计算百分比", () => {
    const s = toPieSlices([25, 75]);
    expect(s[0].percent).toBeCloseTo(25);
    expect(s[1].percent).toBeCloseTo(75);
  });

  it("总和 100%", () => {
    const s = toPieSlices([10, 20, 30, 40]);
    const total = s.reduce((acc, x) => acc + x.percent, 0);
    expect(total).toBeCloseTo(100);
  });

  it("分配颜色", () => {
    const s = toPieSlices([1, 2, 3, 4, 5, 6, 7]);
    expect(s.length).toBe(7);
    // 颜色循环分配
    expect(s[0].color).not.toBe(s[1].color);
  });

  it("全 0 时 percent 为 0（避免 NaN）", () => {
    const s = toPieSlices([0, 0]);
    expect(s[0].percent).toBe(0);
    expect(s[1].percent).toBe(0);
  });
});

/* ----------------------------------------------------------------------------
 * 地图坐标映射纯函数
 * ------------------------------------------------------------------------- */
describe("AipAnalystPage · parseCoords", () => {
  it("正常解析 lat,lng", () => {
    const r = parseCoords("52.21345,-0.94540");
    expect(r).toEqual({ lat: 52.21345, lng: -0.9454 });
  });

  it("带空格", () => {
    const r = parseCoords("52.21, -0.94");
    expect(r).toEqual({ lat: 52.21, lng: -0.94 });
  });

  it("非法格式返回 null", () => {
    expect(parseCoords("abc")).toBeNull();
    expect(parseCoords("123")).toBeNull();
    expect(parseCoords("")).toBeNull();
  });

  it("纬度超范围返回 null", () => {
    expect(parseCoords("91,0")).toBeNull();
    expect(parseCoords("-91,0")).toBeNull();
  });

  it("经度超范围返回 null", () => {
    expect(parseCoords("0,181")).toBeNull();
    expect(parseCoords("0,-181")).toBeNull();
  });
});

describe("AipAnalystPage · projectToMap", () => {
  const bounds = { latMin: 52.0, latMax: 52.4, lngMin: -1.2, lngMax: -0.6 };

  it("中心点映射到中点", () => {
    const p = projectToMap(52.2, -0.9, bounds, 100);
    expect(p.x).toBeCloseTo(50);
    expect(p.y).toBeCloseTo(50);
  });

  it("左下角映射到 (0, size)（y 轴翻转：lat 最小 → y 最大）", () => {
    const p = projectToMap(52.0, -1.2, bounds, 100);
    expect(p.x).toBeCloseTo(0);
    expect(p.y).toBeCloseTo(100);
  });

  it("右上角映射到 (size, 0)（y 轴翻转：lat 最大 → y 最小）", () => {
    const p = projectToMap(52.4, -0.6, bounds, 100);
    expect(p.x).toBeCloseTo(100);
    expect(p.y).toBeCloseTo(0);
  });

  it("自定义 size 参数", () => {
    const p = projectToMap(52.2, -0.9, bounds, 200);
    expect(p.x).toBeCloseTo(100);
    expect(p.y).toBeCloseTo(100);
  });
});

describe("AipAnalystPage · rowsToMarkers", () => {
  const rows: ResultRow[] = [
    { id: "s1", name: "Walter", coords: "52.21,-0.94", rating: 5 },
    { id: "s2", name: "Kuhic", coords: "invalid", rating: 4 },
    { id: "s3", name: "Hickle", coords: "52.20,-0.82", rating: 3 },
  ];

  it("跳过非法坐标", () => {
    const m = rowsToMarkers(rows, "coords", "name");
    expect(m).toHaveLength(2);
    expect(m[0].name).toBe("Walter");
    expect(m[1].name).toBe("Hickle");
  });

  it("保留 intensity 字段", () => {
    const m = rowsToMarkers(rows, "coords", "name");
    expect(m[0].intensity).toBe(5);
  });

  it("空数组返回空", () => {
    expect(rowsToMarkers([], "coords", "name")).toEqual([]);
  });
});

/* ----------------------------------------------------------------------------
 * 表格操作纯函数
 * ------------------------------------------------------------------------- */
describe("AipAnalystPage · sortRows", () => {
  const rows: ResultRow[] = [
    { name: "c", rating: 3 },
    { name: "a", rating: 5 },
    { name: "b", rating: 4 },
  ];

  it("数值升序", () => {
    const r = sortRows(rows, "rating", "asc");
    expect(r.map((x) => x.rating)).toEqual([3, 4, 5]);
  });

  it("数值降序", () => {
    const r = sortRows(rows, "rating", "desc");
    expect(r.map((x) => x.rating)).toEqual([5, 4, 3]);
  });

  it("字符串按字母序", () => {
    const r = sortRows(rows, "name", "asc");
    expect(r.map((x) => x.name)).toEqual(["a", "b", "c"]);
  });

  it("不修改原数组", () => {
    const original = rows.map((r) => r.name);
    sortRows(rows, "name", "desc");
    expect(rows.map((r) => r.name)).toEqual(original);
  });
});

describe("AipAnalystPage · filterRows", () => {
  const rows: ResultRow[] = [
    { name: "Walter", city: "Northampton" },
    { name: "Kuhic", city: "Birmingham" },
    { name: "Hickle", city: "Northampton" },
  ];

  it("关键字匹配", () => {
    expect(filterRows(rows, "north")).toHaveLength(2);
    expect(filterRows(rows, "walter")).toHaveLength(1);
  });

  it("大小写不敏感", () => {
    expect(filterRows(rows, "NORTHAMPTON")).toHaveLength(2);
  });

  it("空关键字返回全部", () => {
    expect(filterRows(rows, "")).toHaveLength(3);
    expect(filterRows(rows, "   ")).toHaveLength(3);
  });

  it("无匹配返回空", () => {
    expect(filterRows(rows, "zzz")).toEqual([]);
  });
});

describe("AipAnalystPage · paginate & totalPages", () => {
  const arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];

  it("第一页返回前 N 个", () => {
    expect(paginate(arr, 1, 5)).toEqual([1, 2, 3, 4, 5]);
  });

  it("第二页返回后续", () => {
    expect(paginate(arr, 2, 5)).toEqual([6, 7, 8, 9, 10]);
  });

  it("最后一页可能不满", () => {
    expect(paginate(arr, 3, 5)).toEqual([11]);
  });

  it("超出页码返回空", () => {
    expect(paginate(arr, 10, 5)).toEqual([]);
  });

  it("totalPages 计算总页数", () => {
    expect(totalPages(11, 5)).toBe(3);
    expect(totalPages(10, 5)).toBe(2);
    expect(totalPages(0, 5)).toBe(1);
  });
});

/* ----------------------------------------------------------------------------
 * 集成：完整结果处理
 * ------------------------------------------------------------------------- */
describe("AipAnalystPage · 集成：filter + sort + paginate", () => {
  const result: QueryResult = {
    columns: [
      { name: "name", type: "string" },
      { name: "rating", type: "number" },
    ],
    rows: [
      { name: "a", rating: 3 },
      { name: "b", rating: 5 },
      { name: "c", rating: 4 },
      { name: "d", rating: 1 },
    ],
    durationMs: 100,
    cacheHit: true,
  };

  it("排序后分页正确", () => {
    const sorted = sortRows(result.rows, "rating", "desc");
    const page1 = paginate(sorted, 1, 2);
    expect(page1.map((r) => r.rating)).toEqual([5, 4]);
  });

  it("过滤后再排序", () => {
    const filtered = filterRows(result.rows, "a");
    expect(filtered).toHaveLength(1);
    const sorted = sortRows(filtered, "rating", "asc");
    expect(sorted[0].rating).toBe(3);
  });
});
