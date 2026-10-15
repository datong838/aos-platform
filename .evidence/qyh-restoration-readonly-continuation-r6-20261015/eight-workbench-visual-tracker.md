# 八台视觉比对接续表 · 2026-10-15

Rules：原稿优先、同尺寸同状态、先方案再改代码、精确Task/Lease、最小更改、保护原数据及用户改动、独立Prime复审。这里只更新比较证据，不新增产品修改。

原稿目录：`/Users/ddt/work/projects/ai_agent/docs/palantier/foundry/html/`。以下区分历史初查与本次复验，不将旧截图冒充当前截图。比较三个视口1280×720、1440×900、1920×1080；业务状态不同只能比较布局，原稿演示数字不能填入实际系统。

|工作台|原稿|已观察及当前判定|后续视觉验收|
|---|---|---|---|
|日常任务总控|workshop-task-cockpit.html|历史1440骨架接近；后续读取终态已另核，完整视觉未验收|实际任务、复盘、共享技能区内部滚动、短窗|
|内容与活动|workshop-content-campaign.html|历史提示遮标题；后续真实输入读取成功时提示不再遮挡，不推导所有失败态已修复|缺来源/读取失败、草稿、风险和审批状态|
|统一运营|workshop-app-order.html|历史三栏接近；真实库存态与原稿退款态不同，详情不可判一致|指标下行文字、真实订单态、内部滚动|
|达人邀约|workshop-creator-outreach.html|后续1280仍有右侧内容超出窗口，P1未解决；1440可见|先修窄窗裁切，再候选、履约及其他页签|
|多媒体生产|workshop-media-studio.html|历史三栏存在；实际数字人页签与原稿文案页签不同，尚无同状态通过结论|文案/短视频/生产评审、长文换行与窄窗|
|经营参谋|workshop-analyst.html|后续真实Case/读取终态有证据；提示占首屏问题保留|说明层级、三阶段/工作区/运行门，不隐藏真实阻断|
|价格治理|workshop-price-governance.html|本次原真人实际三个视口筛选按钮均32px，无重叠/横溢出；单一筛选拉伸P1已修复|辅助失败假0、其他页签、真实非空、键盘焦点；全页未判合格|
|客户关系|workshop-customer.html|历史三栏接近；实际缺来源与原稿客户唤醒执行态不同|正式同意、最小客户资料、计划/产物/日志；不复制演示客户|

原八台初查：`.evidence/qyh-daily-readonly-schema-compat-20261014/browser/visual-comparison.md`。价格本次实际及原稿六图、现场报告、几何与独立复审位于本目录，详见`visual-live-report-r1.md`、`visual-native-geometry-deny-r1.json`、`visual-live-review-consumption-r3.json`。非价格各台没有在本表更新时重新截图，不重复已交付验证。

本次产品唯一改动文件：`apps/web/src/styles/45-ecommerce-workshop.css`，价格primary作用域增加`align-content:start`，提交f036e46c643308651b415179e6e991870dbc26ab。隔离空/非空和真实只读页面证据分别保留；407测试、类型/构建及独立Prime通过只能支持该切片。

Authority AOS-002034，三项正式Delivery回读、七强投影CURRENT、其他38历史Lease保留、唯一写者不变。完整长期Goal ACTIVE；每日及每次aos最新已提交代码和同原权威卷完整PG→API→Web、aos-2不重启继续。八台全视觉与经营首链、原真人最终预算、安装全生命周期和观察发布仍未完成。
