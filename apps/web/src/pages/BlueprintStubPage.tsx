import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";

/** 导航占位页 · 保持侧栏可点，不假装功能已完成 */
export function BlueprintStubPage({
  title,
  blueprintId,
  htmlFile: _htmlFile,
}: {
  title: string;
  blueprintId: string;
  htmlFile: string;
}) {
  return (
    <PageChrome title={title} lede="功能规划中 · 侧栏已对齐导航；业务交互将陆续迁入。">
      <div className="stub-banner">
        参考规格 <code>{blueprintId}</code>
      </div>
      <p className="muted">
        可先使用已接线页：
        <Link to="/workshop/inbox"> 运营台</Link> ·
        <Link to="/aip/drafts"> 提案审批</Link> ·
        <Link to="/ontology"> 本体</Link> ·
        <Link to="/data"> 数据连接</Link>
      </p>
    </PageChrome>
  );
}
