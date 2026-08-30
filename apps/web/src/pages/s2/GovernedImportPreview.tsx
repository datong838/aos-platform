import { useState } from "react";
import { Link } from "react-router-dom";
import { aipMarketplaceImport, type ImportJobMutation, type ImportKind, type ImportPreview, type ImportPreviewRequest } from "../../api/aipMarketplaceImport";
import { PageChrome } from "../../components/PageChrome";

export type ImportForm = {
  sourceId: string; sourceCommit: string; licenseId: string; signatureId: string; sbomId: string; dependencyIds: string; targetId: string; displayName: string;
  sourcePath: string; sourceContent: string; riskLevel: "low" | "medium" | "high" | "critical";
  networkPolicyRef: string; secretRef: string; toolMappings: string; permissionMappings: string; conflictDecisions: string; inputSchema: string; outputSchema: string;
};

export const EMPTY_IMPORT_FORM: ImportForm = {
  sourceId: "", sourceCommit: "", licenseId: "", signatureId: "", sbomId: "", dependencyIds: "", targetId: "", displayName: "", sourcePath: "", sourceContent: "",
  riskLevel: "low", networkPolicyRef: "", secretRef: "", toolMappings: "", permissionMappings: "", conflictDecisions: "", inputSchema: "", outputSchema: "",
};

function parseSchema(value: string, label: string): Record<string, unknown> {
  if (!value.trim()) return {};
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error(`${label} 必须是 JSON 对象`);
  return parsed as Record<string, unknown>;
}
function parseStringMap(value: string, label: string): Record<string, string> {
  const parsed = parseSchema(value, label);
  const invalid = Object.entries(parsed).find(([, item]) => typeof item !== "string" || !item.trim());
  if (invalid) throw new Error(`${label} 的 ${invalid[0]} 必须是非空字符串`);
  return parsed as Record<string, string>;
}
function initialImportForm(): ImportForm {
  const params = new URLSearchParams(window.location.search);
  return {
    ...EMPTY_IMPORT_FORM,
    sourceId: params.get("sourceId") || params.get("packageId") || "",
    targetId: params.get("templateId") || params.get("capabilityId") || "",
    displayName: params.get("displayName") || "",
    licenseId: params.get("licenseId") || "",
  };
}
export function buildImportPreviewRequest(kind: ImportKind, form: ImportForm): ImportPreviewRequest {
  const required = [form.sourceId, form.sourceCommit, form.licenseId, form.signatureId, form.sbomId, form.targetId, form.displayName, form.sourcePath, form.sourceContent];
  if (required.some((value) => !value.trim())) throw new Error("来源、版本、签名、许可证、SBOM、目标标识、名称和源码快照均为必填");
  if (!/^[0-9a-f]{7,64}$/.test(form.sourceCommit.trim())) throw new Error("版本必须是 7–64 位小写十六进制提交号");
  const secretRef = form.secretRef.trim() || null;
  if (secretRef && !/^(vault|secret|keychain):\/\//.test(secretRef)) throw new Error("密钥只能填写 opaque secretRef，禁止明文");
  return {
    kind,
    source: {
      sourceRef: { resourceType: "GitRepository", resourceId: form.sourceId.trim(), revision: form.sourceCommit.trim(), authority: "user-supplied" },
      sourceCommit: form.sourceCommit.trim(), licenseId: form.licenseId.trim(),
      signatureRef: { resourceType: "PackageSignatureVerification", resourceId: form.signatureId.trim(), revision: form.sourceCommit.trim(), authority: "user-supplied" },
      sbomRef: { resourceType: "SBOM", resourceId: form.sbomId.trim(), revision: form.sourceCommit.trim(), authority: "user-supplied" },
      dependencyRefs: form.dependencyIds.split(",").map((value) => value.trim()).filter(Boolean).map((resourceId) => ({ resourceType: "ImportDependency", resourceId, revision: form.sourceCommit.trim(), authority: "user-supplied" })),
      files: [{ path: form.sourcePath.trim(), content: form.sourceContent }],
    },
    mapping: { targetId: form.targetId.trim(), displayName: form.displayName.trim(), toolMappings: parseStringMap(form.toolMappings, "工具映射"), permissionMappings: parseStringMap(form.permissionMappings, "权限映射"), inputSchema: kind === "capability" ? parseSchema(form.inputSchema, "输入 Schema") : {}, outputSchema: kind === "capability" ? parseSchema(form.outputSchema, "输出 Schema") : {} },
    security: { riskLevel: form.riskLevel, networkPolicyRef: form.networkPolicyRef.trim() || null, secretRef },
  };
}

const stepName: Record<string, string> = { source: "1 来源冻结", scan: "2 确定性扫描", mapping: "3 映射合同", security: "4 安全门", test: "5 外部测试" };

export function GovernedImportPreview({ kind }: { kind: ImportKind }) {
  const [form, setForm] = useState<ImportForm>(initialImportForm);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [previewRequest, setPreviewRequest] = useState<ImportPreviewRequest | null>(null);
  const [job, setJob] = useState<ImportJobMutation | null>(null);
  const [testEvidenceId, setTestEvidenceId] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update = (key: keyof ImportForm, value: string) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async () => {
    try {
      setBusy(true);
      const request = buildImportPreviewRequest(kind, form);
      setPreview(await aipMarketplaceImport.previewImport(request));
      setPreviewRequest(request); setJob(null); setError("");
    }
    catch (value) { setPreview(null); setPreviewRequest(null); setJob(null); setError(String((value as Error).message || value)); }
    finally { setBusy(false); }
  };
  const mutate = async (action: () => Promise<ImportJobMutation>) => {
    try { setBusy(true); setJob(await action()); setError(""); }
    catch (value) { setError(String((value as Error).message || value)); }
    finally { setBusy(false); }
  };
  const capability = kind === "capability";
  return (
    <PageChrome title={capability ? "能力受控导入" : "智能体受控导入"} lede="来源冻结 → 扫描与映射 → 独立测试证据 → 审批 → 受控候选 → 精确回滚">
      <div className="notice" role="note" style={{ padding: 12, marginBottom: 14 }}>
        请粘贴已经独立取得的不可变源码快照。系统不会抓取远端或执行源码；通过确定性预检后可建立导入作业，并以独立测试证据完成审批。应用动作只形成可回滚的控制面候选，不调用模型供应商、不发布正式资产。
      </div>
      <section className="card aip-governed-import" style={{ padding: 18 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
          {([
            ["sourceId", "来源资源 ID", "approved/repository"], ["sourceCommit", "精确提交号", "abcdef1"], ["licenseId", "许可证", "MIT"],
            ["signatureId", "签名验证记录", "signature/repository"], ["sbomId", "软件物料清单标识", "sbom/repository"], ["dependencyIds", "依赖标识（逗号分隔）", "tool.catalog.read,policy.tenant"], ["targetId", "目标标识", capability ? "capability.vendor.name" : "agent.vendor.name"], ["displayName", "显示名称", ""], ["sourcePath", "源码相对路径", capability ? "capability.py" : "agent.py"],
          ] as const).map(([key, label, placeholder]) => (
            <label key={key} style={{ display: "grid", gap: 6, fontSize: 13 }}>{label}<input aria-label={label} className="input" value={form[key]} placeholder={placeholder} onChange={(event) => update(key, event.target.value)} /></label>
          ))}
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>风险等级<select aria-label="风险等级" className="input" value={form.riskLevel} onChange={(event) => update("riskLevel", event.target.value)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option><option value="critical">关键</option></select></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>网络策略引用（高/关键必填）<input aria-label="网络策略引用" className="input" value={form.networkPolicyRef} onChange={(event) => update("networkPolicyRef", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>密钥引用（可空）<input aria-label="Secret ref" className="input" value={form.secretRef} placeholder="只填写安全存储引用，不填写密钥正文" onChange={(event) => update("secretRef", event.target.value)} /></label>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 12, marginTop: 12 }}>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>工具映射（JSON）<textarea aria-label="工具映射 JSON" className="input" rows={4} value={form.toolMappings} placeholder='{"source.search":"aos.catalog.read"}' onChange={(event) => update("toolMappings", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>权限映射（JSON）<textarea aria-label="权限映射 JSON" className="input" rows={4} value={form.permissionMappings} placeholder='{"source.read":"aip.asset.read"}' onChange={(event) => update("permissionMappings", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>冲突裁决（JSON）<textarea aria-label="冲突裁决 JSON" className="input" rows={4} value={form.conflictDecisions} placeholder='{"agent.vendor.name":"reuse-existing"}' onChange={(event) => update("conflictDecisions", event.target.value)} /></label>
        </div>
        {capability ? <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>输入 Schema（JSON）<textarea aria-label="输入 Schema JSON" className="input" rows={5} value={form.inputSchema} onChange={(event) => update("inputSchema", event.target.value)} /></label>
          <label style={{ display: "grid", gap: 6, fontSize: 13 }}>输出 Schema（JSON）<textarea aria-label="输出 Schema JSON" className="input" rows={5} value={form.outputSchema} onChange={(event) => update("outputSchema", event.target.value)} /></label>
        </div> : null}
        <label style={{ display: "grid", gap: 6, fontSize: 13, marginTop: 12 }}>源码快照<textarea aria-label="源码快照" className="input" rows={10} value={form.sourceContent} onChange={(event) => update("sourceContent", event.target.value)} /></label>
        <div style={{ display: "flex", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
          <button className="btn primary" type="button" disabled={busy} onClick={() => void submit()}>{busy ? "正在预检…" : "生成预检证据"}</button>
          <Link className="btn" to={capability ? "/aip/capabilities" : "/aip/agent-registry"}>{capability ? "返回能力目录" : "返回智能体目录"}</Link>
        </div>
        {error ? <div className="notice bad" role="alert" style={{ marginTop: 12 }}>{error}</div> : null}
      </section>
      {preview ? <section className="card" style={{ padding: 18, marginTop: 14 }} aria-label="预检证据">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}><h2 style={{ margin: 0 }}>预检 {preview.status === "blocked" ? "受阻" : "等待外部授权"}</h2><code>{preview.previewId}</code></div>
        <p>预检结果：{preview.status === "blocked" ? "需要修正后重新预检" : "可建立受控导入作业"} · 审批：必需</p><details><summary>技术标识（审计用）</summary>内容摘要：<code>{preview.contentHash.slice(0, 16)}…</code></details>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 10 }}>
          {preview.steps.map((step) => <article key={step.step} style={{ border: "1px solid var(--aos-border)", borderRadius: 6, padding: 12 }}><strong>{stepName[step.step] || step.step}</strong><p>{step.status === "passed" ? "通过" : step.status === "blocked" ? "受阻" : "需外部授权"}</p><small>{step.summary}</small>{step.blockerCodes.length ? <ul>{step.blockerCodes.map((code) => <li key={code}><code>{code}</code></li>)}</ul> : null}</article>)}
        </div>
        {preview.scanArtifact.findings.length ? <div className="notice bad" style={{ marginTop: 12 }}>{preview.scanArtifact.findings.map((finding) => <div key={`${finding.ruleId}-${finding.path}-${finding.line}`}>{finding.path}:{finding.line} · {finding.message}（{finding.ruleId}）</div>)}</div> : null}
        {preview.status !== "blocked" && previewRequest && !job ? <button className="btn primary" type="button" disabled={busy} style={{ marginTop: 14 }} onClick={() => void mutate(() => aipMarketplaceImport.createImportJob(preview, previewRequest, parseStringMap(form.conflictDecisions, "冲突裁决")))}>建立导入作业</button> : null}
      </section> : null}
      {job ? <section className="card" style={{ padding: 18, marginTop: 14 }} aria-label="导入作业">
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
          <div><h2 style={{ margin: 0 }}>导入作业 · {job.job.displayName}</h2><p style={{ marginBottom: 0 }}>状态：{{ awaiting_approval: "等待独立测试证据与审批", approved: "已审批，可形成候选", applied: "受控候选已形成", rolled_back: "已精确回滚" }[job.job.status]}</p></div>
          <code>{job.job.jobId}</code>
        </div>
        {job.job.status === "awaiting_approval" ? <div style={{ display: "grid", gridTemplateColumns: "minmax(260px,1fr) auto", gap: 10, alignItems: "end", marginTop: 14 }}>
          <label style={{ display: "grid", gap: 6 }}>独立测试证据 ID<input className="input" aria-label="独立测试证据 ID" value={testEvidenceId} onChange={(event) => setTestEvidenceId(event.target.value)} placeholder="例如 evidence/import-test/2026-08-30" /></label>
          <button className="btn primary" type="button" disabled={busy || !testEvidenceId.trim()} onClick={() => void mutate(() => aipMarketplaceImport.approveImportJob(job.job.jobId, job.job.version, { resourceType: "ImportTestEvidence", resourceId: testEvidenceId.trim(), revision: preview?.contentHash || null, authority: "approved-test-evidence" }, "独立测试证据已复核，批准形成控制面候选"))}>提交审批决定</button>
        </div> : null}
        {job.job.status === "approved" ? <button className="btn primary" type="button" disabled={busy} style={{ marginTop: 14 }} onClick={() => void mutate(() => aipMarketplaceImport.applyImportJob(job.job.jobId, job.job.version))}>形成受控候选</button> : null}
        {job.candidate ? <div className="notice" style={{ marginTop: 14 }}>
          <strong>{job.candidate.displayName}</strong> 已形成{job.candidate.kind === "agent" ? "智能体" : "能力"}候选；候选只保存来源、映射与审批证据，正式发布仍由对应目录完成。
          <div style={{ display: "flex", gap: 10, marginTop: 10, flexWrap: "wrap" }}>
            <Link className="btn" to={capability ? "/aip/capabilities" : "/aip/agent-registry"}>核对正式目录</Link>
            {job.job.status === "applied" ? <button className="btn" type="button" disabled={busy} onClick={() => void mutate(() => aipMarketplaceImport.rollbackImportJob(job.job.jobId, job.job.version, "导入候选验收回滚"))}>回滚本次候选</button> : null}
          </div>
        </div> : null}
        <details style={{ marginTop: 12 }}><summary>Receipt 与对象引用</summary><pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify({ receipt: job.receipt, createdRefs: job.job.createdRefs, compensatedRefs: job.job.compensatedRefs }, null, 2)}</pre></details>
      </section> : null}
    </PageChrome>
  );
}
