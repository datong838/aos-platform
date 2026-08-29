import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpKvList, BpLinkRow, BpTable, BpToolbar } from "./blueprintUi";

type FerryStatus = {
  exportImport?: string; skopeo?: boolean; skopeoMode?: string;
  cosign?: boolean; cosignCliMode?: string; cosignKeyConfigured?: boolean;
  cosignPubConfigured?: boolean; skopeoArchiveEnabled?: boolean;
  imagesManifest?: string | null;
};

type FerryAsset = {
  bundleId: string; platformVersion?: string; contents?: string[];
  compatibleChannels?: string[]; validated?: boolean; createdAt?: string;
};

/** Ferry 只读准备面：实际导出/导入必须从受控变更流程发起。 */
export function FerryPage() {
  const status = useJsonGet<FerryStatus>("/v1/apollo/ferry/status");
  const assets = useJsonGet<{ items?: FerryAsset[] }>("/v1/apollo/assets");
  const rows = Array.isArray(assets.data?.items) ? assets.data.items : [];
  const err = status.err || assets.err;
  return (
    <S2Chrome title="Ferry 摆渡" lede="核验可摆渡资产和本机签名、镜像工具准备状态">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => { status.reload(); assets.reload(); }}>重新读取</button>
        <Link to="/apollo/assets" className="btn-nav">资产包管理 →</Link>
        <Link to="/apollo/change" className="btn-nav">变更审批 →</Link>
      </BpToolbar>
      {err && <BpBanner tone="warn">Ferry 权威读取失败：{err}</BpBanner>}
      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">本机准备状态</h2>
        <BpKvList rows={[
          { key: "导出与导入合同", value: status.data?.exportImport === "200" ? "已注册" : "待核验" },
          { key: "镜像归档工具", value: status.data?.skopeo ? `可用（${status.data.skopeoMode || "已探测"}）` : "不可用" },
          { key: "签名校验工具", value: status.data?.cosign ? `可用（${status.data.cosignCliMode || "已探测"}）` : "不可用" },
          { key: "签名私钥引用", value: status.data?.cosignKeyConfigured ? "已配置" : "未配置" },
          { key: "签名公钥引用", value: status.data?.cosignPubConfigured ? "已配置" : "未配置" },
          { key: "镜像归档", value: status.data?.skopeoArchiveEnabled ? "已启用" : "未启用" },
          { key: "镜像清单", value: status.data?.imagesManifest ? "已配置" : "未配置" },
        ]} />
      </section>
      <section className="bp-domain bp-domain-apollo">
        <h2 className="bp-domain-heading">当前可审计资产（{rows.length}）</h2>
        {rows.length === 0 ? (
          <p className="muted">当前没有已登记资产包；页面不会生成示例 Bundle。请先在资产包管理完成登记和校验。</p>
        ) : (
          <BpTable columns={["资产包", "平台版本", "内容", "兼容通道", "校验"]} rows={rows.map((item) => [
            <span key="id" className="mono">{item.bundleId}</span>,
            <span key="version">{item.platformVersion || "未知"}</span>,
            <span key="contents">{item.contents?.join("、") || "未登记"}</span>,
            <span key="channels">{item.compatibleChannels?.join("、") || "未登记"}</span>,
            <span key="validated">{item.validated ? "已通过" : "待核验"}</span>,
          ])} />
        )}
      </section>
      <BpBanner tone="info">导出、签名、离线传递和目标导入会产生受控运行记录；本页不绕过变更审批直接执行。</BpBanner>
      <BpLinkRow links={[{ to: "/apollo/assets", label: "资产包管理" }, { to: "/apollo/change", label: "变更审批" }, { to: "/apollo", label: "Hub 舰队" }]} />
    </S2Chrome>
  );
}
