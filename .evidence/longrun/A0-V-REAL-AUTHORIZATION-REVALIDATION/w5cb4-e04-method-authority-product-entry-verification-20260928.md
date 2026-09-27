# W5CB4 E04：经营参谋正式方法产品入口验证（2026-09-28）

## 结果

方案 `60de509f`，实现 `74a1fe64`。新增 `/v1/ecommerce/analyst/methods` 的受限 POST、current/exact/Receipt 只读回读，复用原 `EcommerceAnalystAuthorityStore`，没有新表/迁移或第二方法权威。AIP 分析师已有页增加到下级方法配置页的链接；七个经营分析只读视图不改。写请求 tenant/actor 从 Principal 绑定，admin/analyst_editor 才可写，客户端不能传 tenant/actor；算法仅 descriptive_snapshot_v1、结论仅 observation。页面先回读 current 才准提交，提交前持久化幂等键及 createdAt；不入离线队列；任何结果未核清冻结并只读查 Receipt。

## 专项、累计与浏览器

- 后端 `test_ecommerce_analyst_methods_router.py` + `test_ecommerce_analyst_method_authority.py`：25 passed，2 个显式隔离数据库集成测试 skip；路由 manifest：9 passed、2 subtests passed，无新增重复路径。前端 `AnalystMethodPage.test.tsx` + 邻接 `AipAnalystPage.test.tsx`：12 passed；TypeScript noEmit 与 Vite production build 成功。`git diff --check` 无错误。
- 最新 m1 代码配当前 `aos-a0v-recovery-pg-data` 命名卷完成一次全面重启：精确停止旧 8080 与 Vite 进程，重启 `aos-a0v-recovery-pg` 容器；Vite 8434 由既有监督器恢复；`a0v_current_preview_http.py` preflight GREEN，当前 DB `aos_current_preview_20260927`/`a0v_107`、安装 approved、四发布版本、runtime binding=0。新 API 8080 `migrationMode=disabled`、Host=0、worker=0；8080 OpenAPI 与 8434 HTTP 200，18181 无监听。
- 内置浏览器沿 AIP 分析师现有入口打开 `/aip/analyst/methods`；先读 current 得“尚无 r1”，点击一次正式提交后显示 `r1` 和 hash `784dacfa959cfaabc3e2fdf1bb95f367514624e163680e0306896d8914e120c2`，页面重载后再次 current 读回同一 hash。独立 HTTP current 回读的 tenant=`org-org/dev-project`、createdBy=`user:dev`、algorithm=`descriptive_snapshot_v1`、insightKind=`observation`；`dev-org/dev-project` 请求 403。当前 DB 只读计数：方法 head=1、revision=1、`analyst.method_publish` Receipt=1、canary method=0。

## 一致性与风险

符合 231-9 首链“有来源且不宣称因果”的方法版本门，但此方法还未绑定真实 TaskRun、Metric/Evidence、Eval、Logic 或 Provider；不把一个 metadata r1 记成 BG-03/04 已完成。未读商城源库、未运行旧 12 Runs、未启用任何外部动作。当前页面对未知结果保持保守冻结；如果 Receipt 尚无记录，不给重新提交按钮，后续需补正式过期/未受理证明路径，不能让用户手清 localStorage 冒险重发。Method current 读与独立 exact 读为两个只读事务，发布仍以版本 CAS 拒绝并发陈旧写。后续 E05 应优先解决 D01 真正获准数据与 Method/Metric/Evidence 的业务衔接，保留模型/Logic/预算外部门。

## 下一波

E05：复习 231/231-9 与 D01 契约，核现有获准商品主数据及 SourceSelection 正式 Owner 的当前入口，选最小“真实数据截面→有来源分析”生产者，先文件级方案再编码；不把修 37 Skill 或历史旧卷当主线。
