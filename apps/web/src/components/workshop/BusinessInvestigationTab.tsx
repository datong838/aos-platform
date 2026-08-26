import { BUSINESS_INVESTIGATION_READ_FLAG } from "./businessInvestigationFeatureFlags";

export function BusinessInvestigationTab({
  id,
  labelledBy,
}: {
  id: string;
  labelledBy: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={labelledBy}
      className="analyst-panel business-investigation-tab"
      role="tabpanel"
    >
      <header>
        <div>
          <span>Business Investigation · BI-W7-01</span>
          <h2>生意探究</h2>
        </div>
        <strong className="content-campaign-status is-blocked">只读接入中</strong>
      </header>
      <div className="business-investigation-boundary">
        <article>
          <span>能力开关</span>
          <strong>{BUSINESS_INVESTIGATION_READ_FLAG}</strong>
          <p>仅控制工作台只读贡献；命令、周期计划与 Handoff 仍全部关闭。</p>
        </article>
        <article>
          <span>Canonical 聚合</span>
          <strong>尚未装载</strong>
          <p>本页不以静态内容伪造 Case、Run、Data、Evidence 或 Receipt readiness。</p>
        </article>
        <article>
          <span>现有能力</span>
          <strong>七个 Analyst view 保留</strong>
          <p>经营总览、驱动因素、问题诊断、增长计划、效果复盘、证据链与数据质量仍可切换。</p>
        </article>
      </div>
      <aside className="business-investigation-next">
        <strong>下一步：BI-W7-02</strong>
        <p>接入 Case 列表与当前 Case 概览后，才展示真实 tenant-scoped canonical 投影。</p>
      </aside>
    </section>
  );
}
