// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CASE_ID,
  CURRENT_CASE_LIST_FIXTURE,
  INSTALLATION_ID,
  REFERENCE_CASE_ID,
  REFERENCE_CASE_LIST_FIXTURE,
} from "../../../api/integrationCases/fixtures";
import { IntegrationCaseCatalog } from "./IntegrationCaseCatalog";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("IntegrationCaseCatalog", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("renders the current business summary and reports the selected server case", async () => {
    const onSelectCase = vi.fn();
    await act(async () => {
      root.render(
        <IntegrationCaseCatalog
          scope="current"
          items={CURRENT_CASE_LIST_FIXTURE.items}
          selectedCaseId={CASE_ID}
          onSelectCase={onSelectCase}
        />,
      );
    });

    expect(host.textContent).toContain("Current commerce case");
    expect(host.textContent).toContain("证据快照 第 2 版");
    expect(host.textContent).toContain("待处理 1");
    expect(host.textContent).not.toContain(INSTALLATION_ID);
    expect(host.textContent).not.toContain("overlay-7");
    const button = host.querySelector("button") as HTMLButtonElement;
    expect(button.getAttribute("aria-pressed")).toBe("true");
    expect(button.dataset.caseId).toBe(CASE_ID);
    await act(async () => button.click());
    expect(onSelectCase).toHaveBeenCalledWith(CASE_ID);
  });

  it("never renders current-only identity fields for a reference item", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseCatalog
        scope="reference"
        items={REFERENCE_CASE_LIST_FIXTURE.items}
        selectedCaseId={REFERENCE_CASE_ID}
        onSelectCase={() => undefined}
      />,
    );

    expect(html).toContain("Anonymized reference");
    expect(html).toContain("参考接入案例目录");
    expect(html).toContain(`data-case-id=\"${REFERENCE_CASE_ID}\"`);
    expect(html).not.toContain("Owner");
    expect(html).not.toContain("Installation");
    expect(html).not.toContain("Overlay");
    expect(html).not.toContain(INSTALLATION_ID);
  });

  it("fails closed instead of rendering mixed-scope items", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseCatalog
        scope="reference"
        items={CURRENT_CASE_LIST_FIXTURE.items}
        selectedCaseId={null}
        onSelectCase={() => undefined}
      />,
    );

    expect(html).toContain("案例数据作用域不一致，已停止展示");
    expect(html).not.toContain("Current commerce case");
    expect(html).not.toContain(INSTALLATION_ID);
  });

  it("renders a truthful empty state without fixture fallback", () => {
    const html = renderToStaticMarkup(
      <IntegrationCaseCatalog
        scope="current"
        items={[]}
        selectedCaseId={null}
        onSelectCase={() => undefined}
      />,
    );

    expect(html).toContain("暂无当前接入案例");
    expect(html).toContain("当前筛选条件下没有服务端返回的案例");
    expect(html).not.toContain("Current commerce case");
  });
});
