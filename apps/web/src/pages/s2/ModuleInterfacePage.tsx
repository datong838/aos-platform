import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, apiPut, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpKvList,
  BpSplit,
  BpToolbar,
} from "./blueprintUi";

export type FieldDirection = "input" | "output";

export type InterfaceField = {
  id: string;
  name: string;
  type: string;
  direction: FieldDirection;
};

export type ModuleInterfacePayload = {
  moduleId?: string;
  name?: string;
  description?: string;
  entryParams?: Array<Record<string, unknown>>;
  expose?: Record<string, unknown>;
  version?: string;
};

export type ModuleListItem = {
  id: string;
  name: string;
  objectType?: string;
  entryPath?: string;
  widgets?: unknown[];
};

const FIELD_TYPES = ["string", "number", "boolean", "object", "array", "WorkOrder[]", "string[]"] as const;

/** Stable client id for editable rows */
export function newFieldId(): string {
  return `f-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

/** Map API entryParams (key|name + optional direction) → editable fields */
export function paramsToFields(
  params: Array<Record<string, unknown>> | undefined | null,
): InterfaceField[] {
  if (!params?.length) return [];
  return params
    .map((p, i) => {
      const name = String(p.name ?? p.key ?? "").trim();
      if (!name) return null;
      const directionRaw = String(p.direction ?? "input").toLowerCase();
      const direction: FieldDirection = directionRaw === "output" ? "output" : "input";
      return {
        id: `api-${i}-${name}`,
        name,
        type: String(p.type ?? "string"),
        direction,
      } satisfies InterfaceField;
    })
    .filter((x): x is InterfaceField => x != null);
}

/** Serialize editable fields for PUT body */
export function fieldsToEntryParams(fields: InterfaceField[]): Array<Record<string, unknown>> {
  return fields
    .filter((f) => f.name.trim())
    .map((f) => ({
      name: f.name.trim(),
      key: f.name.trim(),
      type: f.type.trim() || "string",
      direction: f.direction,
    }));
}

/** Derive demo fields from module widgets when API fails (演示路径) */
export function deriveMockFields(mod: ModuleListItem | undefined | null): InterfaceField[] {
  const ot = mod?.objectType || "WorkOrder";
  const widgets = (mod?.widgets || []).map((w) => String(w));
  const rows: InterfaceField[] = [
    { id: "mock-in-selection", name: "selection", type: `${ot}[]`, direction: "input" },
  ];
  if (widgets.includes("filters") || widgets.some((w) => w.includes("filter"))) {
    rows.push({ id: "mock-in-filter", name: "filterStatus", type: "string", direction: "input" });
  }
  if (widgets.includes("table") || widgets.some((w) => w.includes("table"))) {
    rows.push({ id: "mock-out-id", name: "selectedId", type: "string", direction: "output" });
  }
  if (widgets.includes("selection")) {
    rows.push({ id: "mock-out-sel", name: "selection", type: `${ot}[]`, direction: "output" });
  }
  if (rows.length === 1) {
    rows.push({ id: "mock-out-id", name: "selectedId", type: "string", direction: "output" });
  }
  return rows;
}

export function displayFieldLabel(field: InterfaceField): string {
  const prefix = field.direction === "output" ? "output" : "input";
  return `${prefix}.${field.name}`;
}

export function ModuleInterfacePage() {
  const { data, err, reload } = useJsonGet<{ items: ModuleListItem[] }>("/v1/modules");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const [ifaceName, setIfaceName] = useState("");
  const [ifaceDesc, setIfaceDesc] = useState("");
  const [ifaceVersion, setIfaceVersion] = useState("1.0.0");
  const [expose, setExpose] = useState<Record<string, unknown>>({});
  const [fields, setFields] = useState<InterfaceField[]>([]);
  const [ifaceLoading, setIfaceLoading] = useState(false);
  const [ifaceErr, setIfaceErr] = useState<string | null>(null);
  const [usingMock, setUsingMock] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const selected = data?.items?.find((m) => m.id === selectedId) || data?.items?.[0];
  const activeId = selected?.id ?? null;

  const loadInterface = useCallback(
    async (moduleId: string, mod: ModuleListItem | undefined) => {
      setIfaceLoading(true);
      setIfaceErr(null);
      setDirty(false);
      try {
        const r = await apiGet<ModuleInterfacePayload>(
          `/v1/modules/${encodeURIComponent(moduleId)}/interface`,
        );
        setIfaceName(r.name || mod?.name || "");
        setIfaceDesc(r.description || "");
        setIfaceVersion(r.version || "1.0.0");
        setExpose(r.expose && typeof r.expose === "object" ? r.expose : {});
        const parsed = paramsToFields(r.entryParams);
        setFields(parsed.length ? parsed : []);
        setUsingMock(false);
      } catch (e) {
        setIfaceErr(String((e as Error).message || e));
        setIfaceName(mod?.name || "");
        setIfaceDesc("");
        setIfaceVersion("1.0.0");
        setExpose({});
        setFields(deriveMockFields(mod));
        setUsingMock(true);
      } finally {
        setIfaceLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    if (!activeId) return;
    void loadInterface(activeId, selected);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload when module id changes
  }, [activeId, loadInterface]);

  async function createMod() {
    await apiPost("/v1/modules", {
      name: "接口台 Module",
      description: "从模块接口页创建",
      objectType: "WorkOrder",
      entryPath: "/workshop/inbox",
      widgets: ["table", "filters", "selection"],
      buddyBound: true,
    });
    setMsg("已创建");
    reload();
  }

  function updateField(id: string, patch: Partial<InterfaceField>) {
    setFields((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
    setDirty(true);
  }

  function removeField(id: string) {
    setFields((prev) => prev.filter((f) => f.id !== id));
    setDirty(true);
  }

  function addField(direction: FieldDirection) {
    setFields((prev) => [
      ...prev,
      {
        id: newFieldId(),
        name: direction === "input" ? "newInput" : "newOutput",
        type: "string",
        direction,
      },
    ]);
    setDirty(true);
  }

  async function saveInterface() {
    if (!activeId) return;
    setSaving(true);
    setMsg("");
    try {
      const body = {
        name: ifaceName || selected?.name || "",
        description: ifaceDesc,
        version: ifaceVersion || "1.0.0",
        entryParams: fieldsToEntryParams(fields),
        expose,
      };
      const r = await apiPut<ModuleInterfacePayload>(
        `/v1/modules/${encodeURIComponent(activeId)}/interface`,
        body,
      );
      setFields(paramsToFields(r.entryParams));
      setIfaceName(r.name || ifaceName);
      setIfaceDesc(r.description || "");
      setIfaceVersion(r.version || "1.0.0");
      setExpose(r.expose && typeof r.expose === "object" ? r.expose : {});
      setUsingMock(false);
      setIfaceErr(null);
      setDirty(false);
      setMsg("接口已保存");
    } catch (e) {
      setMsg(`保存失败：${String((e as Error).message || e)}（可继续本地编辑 · 演示路径）`);
      setUsingMock(true);
    } finally {
      setSaving(false);
    }
  }

  const inputCount = useMemo(() => fields.filter((f) => f.direction === "input").length, [fields]);
  const outputCount = useMemo(() => fields.filter((f) => f.direction === "output").length, [fields]);

  const modules = data?.items || [];

  return (
    <S2Chrome title="Module 接口与嵌套 Loop" lede="定义子 Module 暴露的输入/输出接口，支持 Loop 嵌套渲染。">
      <BpToolbar>
        <label className="mi-module-pick">
          <span className="muted">编辑接口</span>
          <select
            className="mi-input"
            data-testid="mi-module-select"
            value={activeId || ""}
            onChange={(e) => setSelectedId(e.target.value || null)}
            disabled={!modules.length}
          >
            {!modules.length ? <option value="">暂无 Module</option> : null}
            {modules.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => void createMod().catch(console.error)}>
          创建 Module
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => {
            reload();
            if (activeId) void loadInterface(activeId, selected);
          }}
        >
          刷新
        </button>
        <button
          type="button"
          className="btn"
          disabled={!activeId || saving || (usingMock && !dirty)}
          onClick={() => void saveInterface()}
          title={usingMock && !dirty ? "当前为 MOCK 降级，修改后再保存" : undefined}
        >
          {saving ? "保存中…" : dirty ? "保存接口 *" : "保存接口"}
        </button>
        <Link to="/workshop" className="btn-nav">
          应用列表 →
        </Link>
        <Link to="/workshop/canvas" className="btn-nav">
          返回画布 →
        </Link>
      </BpToolbar>

      {usingMock && (
        <BpBanner tone="warn">
          演示路径 · MOCK — 接口 API 不可用或保存失败，当前字段为本地演示数据，可编辑后重试保存。
        </BpBanner>
      )}
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}
      {ifaceErr && !usingMock && <p className="error">{ifaceErr}</p>}

      <BpSplit
        left={
          <div className="bp-object-panel mi-panel">
            <div className="bp-ws-section-title">
              接口定义 · {selected?.name || "维修 Inbox"}
              <span className="mi-counts muted">
                {" "}
                · 入参 {inputCount} / 出参 {outputCount}
              </span>
            </div>

            <div className="mi-meta">
              <label className="mi-meta-field">
                <span>契约名</span>
                <input
                  className="mi-input"
                  value={ifaceName}
                  onChange={(e) => {
                    setIfaceName(e.target.value);
                    setDirty(true);
                  }}
                  disabled={ifaceLoading}
                />
              </label>
              <label className="mi-meta-field">
                <span>版本</span>
                <input
                  className="mi-input"
                  value={ifaceVersion}
                  onChange={(e) => {
                    setIfaceVersion(e.target.value);
                    setDirty(true);
                  }}
                  disabled={ifaceLoading}
                />
              </label>
            </div>

            <div className="mi-field-actions">
              <button type="button" className="btn" onClick={() => addField("input")}>
                + 入参
              </button>
              <button type="button" className="btn" onClick={() => addField("output")}>
                + 出参
              </button>
            </div>

            <table className="mi-table">
              <thead>
                <tr>
                  <th>接口</th>
                  <th>名称</th>
                  <th>类型</th>
                  <th>方向</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {ifaceLoading && (
                  <tr>
                    <td colSpan={5} className="muted">
                      加载中…
                    </td>
                  </tr>
                )}
                {!ifaceLoading && fields.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      暂无字段，点击「+ 入参 / + 出参」添加
                    </td>
                  </tr>
                )}
                {!ifaceLoading &&
                  fields.map((f) => (
                    <tr key={f.id}>
                      <td>
                        <span
                          className={
                            f.direction === "output" ? "mi-label is-output" : "mi-label is-input"
                          }
                        >
                          {displayFieldLabel(f)}
                        </span>
                      </td>
                      <td>
                        <input
                          className="mi-input"
                          value={f.name}
                          aria-label="字段名"
                          onChange={(e) => updateField(f.id, { name: e.target.value })}
                        />
                      </td>
                      <td>
                        <input
                          className="mi-input"
                          list="mi-field-types"
                          value={f.type}
                          aria-label="字段类型"
                          onChange={(e) => updateField(f.id, { type: e.target.value })}
                        />
                      </td>
                      <td>
                        <select
                          className="mi-input"
                          value={f.direction}
                          aria-label="方向"
                          onChange={(e) =>
                            updateField(f.id, {
                              direction: e.target.value === "output" ? "output" : "input",
                            })
                          }
                        >
                          <option value="input">入参</option>
                          <option value="output">出参</option>
                        </select>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="btn mi-btn-danger"
                          aria-label={`删除 ${f.name}`}
                          onClick={() => removeField(f.id)}
                        >
                          删
                        </button>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
            <datalist id="mi-field-types">
              {FIELD_TYPES.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>

            {selected && (
              <BpKvList
                rows={[
                  { key: "entryPath", value: selected.entryPath || "—", mono: true },
                  { key: "objectType", value: selected.objectType || "—" },
                  { key: "moduleId", value: selected.id, mono: true },
                ]}
              />
            )}
          </div>
        }
        right={
          <div className="bp-object-panel">
            <div className="bp-ws-section-title">嵌套 Loop</div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>
              <div>父 Module：{selected?.name || "风险告警管理"}</div>
              <div
                style={{
                  marginLeft: "1rem",
                  borderLeft: "2px solid rgba(56,189,248,0.3)",
                  paddingLeft: "0.75rem",
                  marginTop: 8,
                }}
              >
                <div className="card" style={{ marginBottom: 6 }}>
                  子 Loop · 工单列表行
                </div>
                <div className="card">子 Module · 详情侧栏</div>
              </div>
              <p style={{ marginTop: 8 }}>
                Loop 变量 <code>row</code> 绑定至子 Module <code>input.workOrder</code>
              </p>
            </div>
          </div>
        }
      />

      <BpBanner tone="info">
        嵌套 Module 通过 Interface 契约解耦；Loop 内子 Module 可独立预览与测试。打开业务应用请用{" "}
        <Link to="/workshop">应用列表</Link>，本页只编辑接口契约。
      </BpBanner>
    </S2Chrome>
  );
}
