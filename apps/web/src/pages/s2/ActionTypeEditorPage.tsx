import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";

type ActionType = {
  id: string;
  name: string;
  objectType: string;
  parameters: { name: string; type?: string; required?: boolean }[];
  requiredMarkings: string[];
  submissionCriteria: { field?: string; op?: string }[];
};

const emptyForm = (ot = "WorkOrder"): ActionType => ({
  id: "",
  name: "",
  objectType: ot,
  parameters: [{ name: "reason", type: "string", required: true }],
  requiredMarkings: ["public"],
  submissionCriteria: [{ field: "reason", op: "required" }],
});

function defaultPayloadFromParams(parameters: ActionType["parameters"]): string {
  const obj: Record<string, string> = {};
  for (const p of parameters || []) {
    if (p?.name) obj[p.name] = p.required ? "sample" : "";
  }
  if (Object.keys(obj).length === 0) obj.reason = "ok";
  return JSON.stringify(obj, null, 2);
}

/** 95/96 · Action Type 轻量编辑器 + 试跑校验 */
export function ActionTypeEditorPage() {
  const { actionId = "new" } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const isNew = actionId === "new";
  const [form, setForm] = useState<ActionType>(() => emptyForm(sp.get("ot") || "WorkOrder"));
  const [paramJson, setParamJson] = useState("[]");
  const [markingsText, setMarkingsText] = useState("public");
  const [criteriaJson, setCriteriaJson] = useState("[]");
  const [payloadJson, setPayloadJson] = useState('{\n  "reason": "ok"\n}');
  const [busy, setBusy] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [validateMsg, setValidateMsg] = useState("");
  const [validateErr, setValidateErr] = useState("");

  useEffect(() => {
    if (isNew) {
      const base = emptyForm(sp.get("ot") || "WorkOrder");
      setForm(base);
      setParamJson(JSON.stringify(base.parameters, null, 2));
      setMarkingsText(base.requiredMarkings.join(", "));
      setCriteriaJson(JSON.stringify(base.submissionCriteria, null, 2));
      setPayloadJson(defaultPayloadFromParams(base.parameters));
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<ActionType>(`/v1/actions/types/${encodeURIComponent(actionId)}`);
        if (cancelled) return;
        setForm(row);
        setParamJson(JSON.stringify(row.parameters || [], null, 2));
        setMarkingsText((row.requiredMarkings || []).join(", "));
        setCriteriaJson(JSON.stringify(row.submissionCriteria || [], null, 2));
        setPayloadJson(defaultPayloadFromParams(row.parameters || []));
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [actionId, isNew, sp]);

  function patch<K extends keyof ActionType>(key: K, value: ActionType[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const id = form.id.trim();
      if (!id) throw new Error("请填写 id");
      if (!form.name.trim()) throw new Error("请填写 name");
      let parameters: ActionType["parameters"];
      let submissionCriteria: ActionType["submissionCriteria"];
      try {
        parameters = JSON.parse(paramJson) as ActionType["parameters"];
        if (!Array.isArray(parameters)) throw new Error("parameters 须为数组");
      } catch {
        throw new Error("parameters JSON 无效");
      }
      try {
        submissionCriteria = JSON.parse(criteriaJson) as ActionType["submissionCriteria"];
        if (!Array.isArray(submissionCriteria)) throw new Error("criteria 须为数组");
      } catch {
        throw new Error("submissionCriteria JSON 无效");
      }
      const requiredMarkings = markingsText
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      const body = {
        id,
        name: form.name.trim(),
        objectType: form.objectType.trim() || "WorkOrder",
        parameters,
        requiredMarkings,
        submissionCriteria,
      };
      if (isNew) {
        await apiPost("/v1/actions/types", body);
        setMsg(`已创建 ${id}`);
        navigate(`/ontology/action-types/${encodeURIComponent(id)}`, { replace: true });
      } else {
        await apiPut(`/v1/actions/types/${encodeURIComponent(id)}`, body);
        setMsg("已保存");
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function runValidate() {
    setValidateBusy(true);
    setValidateMsg("");
    setValidateErr("");
    try {
      const id = form.id.trim();
      if (!id || isNew) throw new Error("请先创建并保存 Action Type");
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(payloadJson) as Record<string, unknown>;
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          throw new Error("payload 须为对象");
        }
      } catch {
        throw new Error("试跑 payload JSON 无效");
      }
      const res = await apiPost<{ ok?: boolean; actionTypeId?: string }>("/v1/actions/validate", {
        actionTypeId: id,
        payload,
      });
      setValidateMsg(res.ok ? `校验通过 · ${res.actionTypeId || id}` : "校验返回非 ok");
    } catch (e) {
      const errObj = e as Error & { body?: { details?: unknown; message?: string } };
      const details = errObj.body?.details;
      const detailText =
        details != null ? ` · ${typeof details === "string" ? details : JSON.stringify(details)}` : "";
      setValidateErr(`${errObj.message || String(e)}${detailText}`);
    } finally {
      setValidateBusy(false);
    }
  }

  return (
    <S2Chrome
      title={isNew ? "新建 Action Type" : `Action Type · ${form.id}`}
      lede="元数据编辑 · 试跑基于已保存 criteria · 参数以 JSON 轻量维护"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 发现
          </Link>
          {form.objectType && (
            <Link
              to={`/ontology/object-types/${encodeURIComponent(form.objectType)}`}
              className="btn-nav"
            >
              所属 OT →
            </Link>
          )}
          <button type="button" className="btn-primary" disabled={busy} onClick={() => void save()}>
            {busy ? "保存中…" : isNew ? "创建" : "保存"}
          </button>
          {!isNew && (
            <button
              type="button"
              className="btn-nav"
              disabled={validateBusy || busy}
              onClick={() => void runValidate()}
            >
              {validateBusy ? "校验中…" : "试跑校验"}
            </button>
          )}
        </BpToolbar>
        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}
        <BpBanner tone="info">
          试跑调用已保存的 submissionCriteria / markings（不是表单草稿）。改 criteria 后请先保存再试跑。
          修改 objectType 会影响 Draft 绑定。
        </BpBanner>
        <div className="ont-form-grid" style={{ marginTop: "0.75rem" }}>
          <label className="ont-form-field">
            <span>id</span>
            <input
              className="aos-input"
              value={form.id}
              disabled={!isNew}
              onChange={(e) => patch("id", e.target.value)}
              placeholder="CloseWorkOrder"
            />
          </label>
          <label className="ont-form-field">
            <span>name</span>
            <input className="aos-input" value={form.name} onChange={(e) => patch("name", e.target.value)} />
          </label>
          <label className="ont-form-field">
            <span>objectType</span>
            <input
              className="aos-input"
              value={form.objectType}
              onChange={(e) => patch("objectType", e.target.value)}
            />
          </label>
          <label className="ont-form-field">
            <span>requiredMarkings（逗号分隔）</span>
            <input
              className="aos-input"
              value={markingsText}
              onChange={(e) => setMarkingsText(e.target.value)}
            />
          </label>
          <label className="ont-form-field ont-form-span">
            <span>parameters（JSON）</span>
            <textarea
              className="aos-input"
              rows={6}
              value={paramJson}
              onChange={(e) => setParamJson(e.target.value)}
              style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" }}
            />
          </label>
          <label className="ont-form-field ont-form-span">
            <span>submissionCriteria（JSON）</span>
            <textarea
              className="aos-input"
              rows={4}
              value={criteriaJson}
              onChange={(e) => setCriteriaJson(e.target.value)}
              style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" }}
            />
          </label>
          {!isNew && (
            <label className="ont-form-field ont-form-span">
              <span>试跑 payload（JSON）· 不落库</span>
              <textarea
                className="aos-input"
                rows={5}
                value={payloadJson}
                onChange={(e) => setPayloadJson(e.target.value)}
                style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" }}
              />
            </label>
          )}
        </div>
        {!isNew && (
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              className="btn-nav"
              disabled={validateBusy || busy}
              onClick={() => void runValidate()}
            >
              {validateBusy ? "校验中…" : "试跑校验（已保存规则）"}
            </button>
            {validateMsg && <p className="bp-prop-ok">{validateMsg}</p>}
            {validateErr && <p className="error">{validateErr}</p>}
          </div>
        )}
      </div>
    </S2Chrome>
  );
}
