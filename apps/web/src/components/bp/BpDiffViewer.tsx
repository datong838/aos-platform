import { useMemo } from "react";

type DiffLineKind = "add" | "del" | "context";

type DiffLine = {
  kind: DiffLineKind;
  oldNo?: number;
  newNo?: number;
  text: string;
};

/** 行级 LCS diff（O(n*m) 内存优化为 2 行） */
function computeDiff(before: string, after: string): DiffLine[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const n = a.length;
  const m = b.length;
  const prev = new Array<number>(m + 1).fill(0);
  const curr = new Array<number>(m + 1).fill(0);
  const dp: Uint16Array[] = [];
  for (let i = 0; i <= n; i++) {
    const row = new Uint16Array(m + 1);
    for (let j = 0; j <= m; j++) {
      if (i === 0) row[j] = 0;
      else if (j === 0) row[j] = 0;
      else if (a[i - 1] === b[j - 1]) row[j] = prev[j - 1] + 1;
      else row[j] = Math.max(prev[j], curr[j - 1]);
    }
    dp.push(row);
    for (let j = 0; j <= m; j++) prev[j] = row[j];
    for (let j = 0; j <= m; j++) curr[j] = 0;
  }
  // 回溯
  const result: DiffLine[] = [];
  let i = n;
  let j = m;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift({ kind: "context", oldNo: i, newNo: j, text: a[i - 1] });
      i--;
      j--;
    } else if (dp[i - 1][j] >= dp[i][j - 1]) {
      result.unshift({ kind: "del", oldNo: i, text: a[i - 1] });
      i--;
    } else {
      result.unshift({ kind: "add", newNo: j, text: b[j - 1] });
      j--;
    }
  }
  while (i > 0) {
    result.unshift({ kind: "del", oldNo: i, text: a[i - 1] });
    i--;
  }
  while (j > 0) {
    result.unshift({ kind: "add", newNo: j, text: b[j - 1] });
    j--;
  }
  return result;
}

export function BpDiffViewer({
  before,
  after,
  mode = "unified",
  language,
  title = "差异对比",
}: {
  before: string;
  after: string;
  mode?: "unified" | "split";
  language?: string;
  title?: string;
}) {
  const lines = useMemo(() => computeDiff(before, after), [before, after]);
  const additions = useMemo(() => lines.filter((l) => l.kind === "add").length, [lines]);
  const deletions = useMemo(() => lines.filter((l) => l.kind === "del").length, [lines]);

  if (mode === "split") {
    const left = lines.filter((l) => l.kind !== "add");
    const right = lines.filter((l) => l.kind !== "del");
    return (
      <div className="bp-diff">
        <div className="bp-diff-header">
          {title} · <span style={{ color: "var(--aos-green)" }}>+{additions}</span> ·{" "}
          <span style={{ color: "var(--aos-red)" }}>-{deletions}</span>
          {language ? ` · ${language}` : ""}
        </div>
        <div className="bp-diff-split">
          <div>
            {left.map((l, i) => (
              <DiffRowUnified key={i} line={l} />
            ))}
          </div>
          <div className="bp-diff-split-sep" />
          <div>
            {right.map((l, i) => (
              <DiffRowUnified key={i} line={l} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bp-diff">
      <div className="bp-diff-header">
        {title} · <span style={{ color: "var(--aos-green)" }}>+{additions}</span> ·{" "}
        <span style={{ color: "var(--aos-red)" }}>-{deletions}</span>
        {language ? ` · ${language}` : ""}
      </div>
      {lines.map((l, i) => (
        <DiffRowUnified key={i} line={l} />
      ))}
    </div>
  );
}

function DiffRowUnified({ line }: { line: DiffLine }) {
  const cls =
    line.kind === "add" ? "bp-diff-line bp-diff-line-add" : line.kind === "del" ? "bp-diff-line bp-diff-line-del" : "bp-diff-line bp-diff-line-context";
  const sign = line.kind === "add" ? "+" : line.kind === "del" ? "-" : " ";
  const gutter = line.newNo ?? line.oldNo ?? "";
  return (
    <div className={cls}>
      <span className="bp-diff-gutter">{gutter}</span>
      <span className="bp-diff-content">
        {sign} {line.text}
      </span>
    </div>
  );
}
