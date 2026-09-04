# R4-O04 verification

- 真实租户：`org-org/dev-project`；负租户：`dev-org/dev-project`。
- 工作区回读：订单 50、库存 50、履约 19、售后 0、支付 50、已有案例 0；内部处理候选 9。
- 真实浏览器内部提案：初始 `proposal-21d7262dfe874bee9707`，修改后替代提案 `proposal-b83c4cd60a9d44ea969c`，第 1 版，提案 hash `5c3d9d176d54ca239d637082f76f15f2ab91c73983acb3378a5133d4c38ac268`。
- 功能链：修改、采纳建议、替代提案、审批预览、日志回读、撤回全部成功；未获取执行租约，未执行退款、发货、调价、发布或客户触达。
- Web 专项：运营内部流程、公共外壳、宿主与页头联动通过；全量：272 files / 2452 tests passed。
- API 专项与邻接：51 tests passed。
- TypeScript、Vite production build（370 modules）、`git diff --check`：GREEN。
- 视觉：1280×720 内置浏览器与同视口视觉稿组合对照通过；公共外壳不再在业务首屏前插入技术状态卡，完整侧栏和三栏业务工作区均可见，详见根目录 `design-qa.md`。
