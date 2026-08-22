import { useState } from "react";
import { Link } from "react-router-dom";
import { aipMarketplaceImport, type ImportKind, type ImportPreview, type ImportPreviewRequest } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";

export type ImportForm = {
  sourceId: string; sourceCommit: string; licenseId: string; sbomId: string; targetId: string; displayName: string;
  sourcePath: string; sourceContent: string; riskLevel: "low" | "medium" | "high" | "critical";
  networkPolicyRef: string; secretRef: string; inputSchema: string; outputSchema: string;
};

export const EMPTY_IMPORT_FORM: ImportForm = {
  sourceId: "", sourceCommit: "", licenseId: "", sbomId: "", targetId: "", displayName: "", sourcePath: "", sourceContent: "",
  riskLevel: "low", networkPolicyRef: "", secretRef: "", inputSchema: "", outputSchema: "",
};

function parseSchema(value: string, label: string): Record<string, unknown> {
  if (!value.trim()) return {};
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} 必须是 JSON 对象`);
  return parsed as Record<string, unknown>;
}
export function buildImportPreviewRequest(kind: ImportKind, form: ImportForm): ImportPreviewRequest {
  const required = [form.sourceId, form.sourceCommit, form.licenseId, form.sbomId, form.targetId, form.displayName, form.sourcePath, form.sourceContent];
  if (required.some((value) => !value.trim())) throw new Error("来源、版本、许可证、SBOM、目标标识、名称和源码快照均为必填");
  if (!/^[0-9a-f]{7,64}$/.test(form.sourceCommit.trim())) throw new Error("版本必须是 7–64 位小写十六进制提交号");
  const secretRef = form.secretRef.trim() || null;
  if (secretRef && !/^(vault|secret|keychain):\/\//.test(secretRef)) throw new Error("密钥只能填写 opaque secretRef，禁止明文");
  return {
    kind,
    source: {
      sourceRef: { resourceType: "GitRepository", resourceId: form.sourceId.trim(), revision: form.sourceCommit.trim(), authority: "user-supplied" },
      sourceCommit: form.sourceCommit.trim(), licenseId: form.licenseId.trim(),
      sbomRef: { resourceType: "SBOM", resourceId: form.sbomId.trim(), revision: form.sourceCommit.trim(), authority: "user-supplied" },
      files: [{ path: form.sourcePath.trim(), content: form.sourceContent }],
    },
    mapping: { targetId: form.targetId.trim(), displayName: form.displayName.trim(), toolMappings: {}, permissionMappings: {}, inputSchema: kind === "capability" ? parseSchema(form.inputSchema, "输入 Schema") : {}, outputSchema: kind === "capability" ? parseSchema(form.outputSchema, "输出 Schema") : {} },
    security: { riskLevel: form.riskLevel, networkPolicyRef: form.networkPolicyRef.trim() || null, secretRef },
  };
}

const stepName: Record<string, string> = { source: "1 来源冻结", scan: "2 确定性扫描", mapping: "3 映射合同", security: "4 安全门", test: "5 外部测试" };

export function GovernedImportPreview({ kind }: { kind: ImportKind }) {
  const [form, setForm] = useState<ImportForm>(EMPTY_IMPORT_FORM);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update = (key: keyof ImportForm, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    try { setBusy(true); setPreview(await aipMarketplaceImport.previewImport(buildImportPreviewRequest(kind, form))); setError(""); }
    catch (value) { setPreview(null); setError(String((value as Error).message || value)); }
    finally { setBusy(false); }
  };
  const capability = kind === "capability";
  return (
    <PageChrome title={capability ? "能力导入预检" : "智能体导入预检"} lede="五步证据化预检 · 不抓取远端、不执行源码、不创建 ImportJob、不直接安装">
      <div className="notice" role="note" style={{ padding: 12, marginBottom: 14 }}>
        请粘贴已经独立取得的不可变源码快照。预检只做确定性扫描和合同校验；连通测试、Provider 调用、ImportJob、审批及安装均保持未执行。
      </div>
      <section className="card" style={{ padding: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
          {([
            ["sourceId", "来源资源 ID", "approved/repository"], ["sourceCommit", "精确提交号", "abcdef1"], ["licenseId", "许可证", "MIT"],
            ["sbomId", "SBOM 资源 ID", "sbom/repository"], ["targetId", "目标标识", capability ? "capability.vendor.name" : "agent.vendor.name"], ["displayName", "显示名称", ""], ["sourcePath", "源码相对路径", capability ? "capability.py" : "agent.py"],
          ] as const).map(([key, label, placeholder]) => (
            <label key={key} style={{ display: "grid", gap: 6, fontSize: 13 }}>{label}<input className="input" value={form[key]} placeholder={placeholder} onChange={(event) => update(key, event.target.value)} /></label>
          ))}
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>风险等级<select className="input" value={form.riskLevel} onChange={(event) => update("riskLevel", event.target.value)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="critical">关键</option></select></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>网络策略引用（高/关键必填）<input className="input" value={form.networkPolicyRef} onChange={(event) => update("networkPolicyRef", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>Secret ref（可空）<input className="input" value={form.secretRef} placeholder="keychain://service/account" onChange={(event) => update("secretRef", event.target.value)} /></label>
        </div>
        {capability ? <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>输入 Schema（JSON）<textarea className="input" rows={5} value={form.inputSchema} onChange={(event) => update("inputSchema", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>输出 Schema（JSON）<textarea className="input" rows={5} value={form.outputSchema} onChange={(event) => update("outputSchema", event.target.value)} /></label>
        </div> : null}
        <label style={{ display: "grid", gap: 6, fontSize: 13, marginTop: 12 }}>源码快照<textarea className="input" rows={10} value={form.sourceContent} onChange={(event) => update("sourceContent", event.target.value)} /></label>
        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <button className="btn primary" type="button" disabled={busy} onClick={() => void submit()}>{busy ? "正在预检…" : "生成预检证据"}</button>
          <Link className="btn" to={capability ? "/aip/capabilities" : "/aip/agent-registry"}>{capability ? "返回能力目录" : "返回智能体目录"}</Link>
        </div>
        {error ? <div className="notice bad" role="alert" style={{ marginTop: 12 }}>{error}</div> : null}
      </section>
      {preview ? <section className="card" style={{ padding: 18, marginTop: 14 }} aria-label="预检证据">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><h2 style={{ margin: 0 }}>预检 {preview.status === "blocked" ? "受阻" : "等待外部授权"}</h2><code>{preview.previewId}</code></div>
        <p>ImportJob 权威：未创建 · 审批：必需 · 内容哈希：<code>{preview.contentHash.slice(0, 16)}…</code></p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 10 }}>
          {preview.steps.map((step) => <article key={step.step} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 12 }}><strong>{stepName[step.step] || step.step}</strong><p>{step.status === "passed" ? "通过" : step.status === "blocked" ? "受阻" : "需外部授权"}</p><small>{step.summary}</small>{step.blockerCodes.length ? <ul>{step.blockerCodes.map((code) => <li key={code}><code>{code}</code></li>)}</ul> : null}</article>)}
        </div>
        {preview.scanArtifact.findings.length ? <div className="notice bad" style={{ marginTop: 12 }}>{preview.scanArtifact.findings.map((finding) => <div key={`${finding.ruleId}-${finding.path}-${finding.line}`}>{finding.path}:{finding.line} · {finding.message}（{finding.ruleId}）</div>)}</div> : null}
      </section> : null}
    </PageChrome>
  );
}
