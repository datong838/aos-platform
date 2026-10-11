import { Link } from "react-router-dom";
import type { InstallationListItem, InstallationState } from "../../api/assetControl/types";
import { useInstallations, useRuntimeInstallation } from "../../pages/s2/assetBundles/readHooks";

const labels: Record<InstallationState, string> = {
  draft: "草稿", submitted: "待批准", approved: "已批准", rejected: "已退回",
  applied: "待验证", active: "已激活", rolled_back: "已回滚", uninstalled: "已卸载",
};

function InstallationRow({ installation }: { installation: InstallationListItem }) {
  const state = useRuntimeInstallation(installation.installationId);
  const runtime = state.data;
  const current = state.status === "ready" && !state.stale && !state.refreshing
    && runtime?.installationId === installation.installationId
    && runtime.installationRevision === installation.currentRevision
    && runtime.installationEtag === installation.etagVersion
    && runtime.installationState === installation.state;
  return (
    <li>
      <strong>{installation.displayName}</strong> · {labels[installation.state]}
      {current && runtime.effectiveState === "not_prepared" && runtime.binding === null
        ? <p>运行资源尚未准备。批准安装后仍需完成运行准备、验证和配置，工作台才会出现在目录中。</p>
        : <p>{current ? "请在安装管理中核对运行状态、配置与访问权限。" : "运行状态尚未核验，请在安装管理中查看或重新读取。"}</p>}
    </li>
  );
}

/** Mounted with a session identity key by the catalog host; reads never activate an installation. */
export function WorkshopInstallationDiagnosis() {
  const state = useInstallations({ limit: 5, offset: 0 });
  const current = (state.status === "ready" || state.status === "empty") && !state.stale && !state.refreshing;
  return (
    <section aria-label="工作区安装状态">
      <h2>当前工作区安装状态</h2>
      <p>下面是当前账号可见的安装记录。工作台入口还取决于安装、运行配置和访问权限。</p>
      {current && state.data
        ? state.data.items.length > 0
          ? <><ul>{state.data.items.map(item => <InstallationRow key={item.installationId} installation={item} />)}</ul>{state.data.total > state.data.items.length && <p>更多记录请在安装管理中查看。</p>}</>
          : <p>当前账号没有可见安装记录；不能据此判断其他账号或组织是否已安装。</p>
        : <p role="status">{state.status === "loading" || state.status === "idle" ? "正在读取安装状态…" : "安装状态尚未核验，请查看访问权限或重新读取。"}</p>}
      <p>打开资产包管理后，选择“安装管理”中的记录，查看运行状态与配置条件。</p>
      <Link to="/apollo/assets">打开资产包管理</Link>
      <button type="button" onClick={state.reload}>重新读取安装状态</button>
    </section>
  );
}
