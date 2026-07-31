import { OverviewDomainGrid } from "../components/OverviewDomainGrid";
import { PageChrome } from "../components/PageChrome";

/**
 * 226 · 严格对齐 foundry/html/index.html 主内容区
 * （无指标条 / 无工具栏 / 900px 居中）
 */
export function OverviewPage() {
  return (
    <PageChrome
      title="数据操作系统 · 本体数字孪生 · AIP 人工智能平台 · 工作台"
      titleTone="brand"
      lede={
        <>
          日常从 <span className="ov-em-blue">工作台</span> 进入；建设路径：连接器 → 管道 → 数据集 → OKF / 本体 →{" "}
          <span className="ov-em-amber">AIP</span> → <span className="ov-em-blue">工作台（操作台）</span>。
        </>
      }
    >
      <div className="overview-page" style={{ maxWidth: "900px", margin: "0 auto" }}>
        <OverviewDomainGrid />
      </div>
    </PageChrome>
  );
}
