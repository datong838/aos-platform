import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright-core";

const outputDir = path.dirname(new URL(import.meta.url).pathname);
const browser = await chromium.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: true,
});
const results = [];

try {
  for (const viewport of [
    { width: 1280, height: 720 },
    { width: 1440, height: 900 },
    { width: 1920, height: 1080 },
  ]) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const failures = [];
    page.on("pageerror", (error) => failures.push(`pageerror:${error.message}`));
    page.on("response", (response) => {
      if (response.status() >= 500) failures.push(`http:${response.status()}:${response.url()}`);
    });

    await page.goto("http://127.0.0.1:15173/apollo/assets", { waitUntil: "networkidle" });
    await page.getByRole("tab", { name: "安装管理" }).click();
    await page.waitForTimeout(1200);
    const installationChoice = page.getByRole("button", { name: "查看事件" }).first();
    if ((await installationChoice.count()) === 0) {
      await page.screenshot({ path: path.join(outputDir, `diagnostic-${viewport.width}x${viewport.height}.png`) });
      throw new Error(`安装列表未出现：${(await page.locator("body").innerText()).slice(-1200)}`);
    }
    await installationChoice.click();
    await page.getByText("栖月汇电商工作台 · 八 Module canonical successor", { exact: true }).last().waitFor();
    await page.getByText("runtime_storage_unavailable", { exact: true }).waitFor();
    await page.getByText("当前环境尚未安装运行存储；安装事实可读，运行操作保持关闭。", { exact: true }).scrollIntoViewIfNeeded();

    await page.getByRole("button", { name: "折叠侧栏" }).click();
    await page.getByRole("button", { name: "展开侧栏" }).waitFor();
    await page.getByRole("button", { name: "展开侧栏" }).click();
    await page.getByRole("button", { name: "折叠侧栏" }).waitFor();

    const actions = await page.getByRole("button", { name: /^(运行准备|校验准备|配置|启用|停用)$/ }).count();
    const runtimeReasonVisible = await page
      .getByText("当前环境尚未安装运行存储；安装事实可读，运行操作保持关闭。", { exact: true })
      .isVisible();
    await page.screenshot({
      path: path.join(outputDir, `asset-control-${viewport.width}x${viewport.height}.png`),
      fullPage: true,
    });
    results.push({ viewport, failures, runtimeReasonVisible, runtimeActionButtonCount: actions });
    await context.close();
  }
} finally {
  await browser.close();
}

const evidence = {
  schemaVersion: "aos.browser-acceptance/ar1-d-v1",
  target: "http://127.0.0.1:15173/apollo/assets",
  tenant: "org-org/dev-project",
  result: results.every(
    (item) => item.failures.length === 0 && item.runtimeReasonVisible && item.runtimeActionButtonCount === 0,
  )
    ? "PASS"
    : "FAIL",
  results,
  boundaries: [
    "内置浏览器已完成真实栖月汇安装详情、侧栏折叠展开和滚动实点；本脚本补充三视口布局证据。",
    "审计 API 为只读进程，未执行安装、运行、Provider、计费或发布写操作。",
  ],
};
fs.writeFileSync(path.join(outputDir, "browser-acceptance.json"), `${JSON.stringify(evidence, null, 2)}\n`);
console.log(JSON.stringify(evidence, null, 2));
if (evidence.result !== "PASS") process.exitCode = 1;
