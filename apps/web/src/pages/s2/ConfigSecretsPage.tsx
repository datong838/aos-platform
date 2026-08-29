import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { BpBanner, BpKvList, BpTable, BpToolbar } from "./blueprintUi";

type ConfigItem = { key: string; source?: string; description?: string; sensitive?: boolean; valueRef?: string | null };
type ConfigResponse = { vaultRefsOnly?: boolean; plaintextRejected?: boolean; items?: ConfigItem[]; maintenanceWindow?: null | { start?: string; end?: string; status?: string }; authority?: string };

export function ConfigSecretsPage() {
  const response = useJsonGet<ConfigResponse>("/v1/apollo/config");
  const items = Array.isArray(response.data?.items) ? response.data.items : [];
  return (
    <S2Chrome title="配置与密钥" lede="查看当前工作区已登记的配置元数据与密钥保护策略">
      <BpToolbar><button type="button" className="btn" onClick={response.reload}>重新读取</button><Link to="/apollo/change" className="btn-nav">创建配置变更 →</Link></BpToolbar>
      {response.err && <BpBanner tone="warn">配置权威读取失败：{response.err}</BpBanner>}
      <section className="bp-domain bp-domain-apollo"><h2 className="bp-domain-heading">保护策略</h2><BpKvList rows={[
        { key: "密钥存储", value: response.data?.vaultRefsOnly ? "只接受密钥引用" : "待核验" },
        { key: "明文密钥", value: response.data?.plaintextRejected ? "拒绝接收" : "待核验" },
        { key: "配置 authority", value: response.data?.authority === "not_configured" ? "尚未配置" : response.data?.authority || "未知" },
        { key: "维护窗口", value: response.data?.maintenanceWindow ? "已登记" : "尚未登记" },
      ]} /></section>
      <section className="bp-domain bp-domain-apollo"><h2 className="bp-domain-heading">配置元数据（{items.length}）</h2>{items.length === 0 ? <p className="muted">当前没有可审计配置项；页面不会生成模型、连接池、密钥或维护窗口示例。</p> : <BpTable columns={["配置项", "来源", "说明", "敏感"]} rows={items.map((item) => [<span key="k" className="mono">{item.key}</span>, <span key="s">{item.source || "未知"}</span>, <span key="d">{item.description || "未填写"}</span>, <span key="p">{item.sensitive ? "是" : "否"}</span>])} />}</section>
      <BpBanner tone="warn">页面永不读取或显示密钥正文。新增或修改配置必须通过变更审批并只提交 opaque 引用。</BpBanner>
    </S2Chrome>
  );
}
