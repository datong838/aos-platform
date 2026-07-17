import { Link } from "react-router-dom";
import { PageChrome } from "../components/PageChrome";

/** T-UI S2 stub — keeps DEMO_PAGES navigable without fake “done” UX */
export function BlueprintStubPage({
  title,
  blueprintId,
  htmlFile,
}: {
  title: string;
  blueprintId: string;
  htmlFile: string;
}) {
  return (
    <PageChrome
      title={title}
      lede="蓝图占位页 · 侧栏已对齐 foundry/html；业务交互按 T-UI S2 迁入。"
    >
      <div className="stub-banner">
        蓝图 id=<code>{blueprintId}</code> · 参考{" "}
        <code>docs/palantier/foundry/html/{htmlFile}</code>
      </div>
      <p className="muted">
        主路径可先用已接线页：
        <Link to="/workshop/inbox"> 运营台</Link> ·
        <Link to="/aip/drafts"> Draft</Link> ·
        <Link to="/ontology"> 本体</Link> ·
        <Link to="/data"> 数据连接</Link>
      </p>
    </PageChrome>
  );
}
