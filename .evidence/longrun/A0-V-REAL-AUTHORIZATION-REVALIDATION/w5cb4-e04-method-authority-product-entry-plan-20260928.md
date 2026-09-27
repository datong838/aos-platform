# W5CB4 E04：经营参谋正式方法版本产品入口计划（2026-09-28）

## 上位复习与进入事实

归属 231 A1/BG-03，服务 231-9 第 2/3/7/8 节的“有来源建议/方法版本”；复用 W3-13 `MethodRevision` Owner，不造第二套方法表。E03 已证当前租户 MethodRevision=0，Owner 的 tenant、哈希、版本 CAS、advisory lock、Receipt 可用；模型、Logic、业务数据仍有独立门。本波只让业务用户从产品入口创建/精确读回**描述性观察方法元数据**，不运行分析、不发布 Skill、不构造业务结论。

## 文件门与实现顺序

1. 后端：新增 `services/aos-api/aos_api/routers/ecommerce_analyst_methods.py`（正式 POST/GET current/exact/Receipt 回读）；仅给 `ecommerce_analyst_authority_store.py` 加只读 current/Receipt 方法，修改 `routers/domain_manifest.json` 并由生成器重建 `routers/domain_aggregates.py`。改前哈希分别为新增、`a059e798d97ee3e76058767dc8683fb8bba9ae4d`、`98ec499d275656241e6b75000a61aed83fa279e3`、`625b9fed9133a91f0d6e14b85f6c47d44c462fda`。不改发布交易和迁移。
2. 身份/请求：从 `Principal` 取 tenant、subject；写入要求 admin 或可信 analyst/editor 角色（先核现有角色）；`Idempotency-Key` 必填；客户端不能指定另一个 actor/tenant，服务端组装 createdBy/tenant/createdAt/contentHash 或严格对照；只接收 `descriptive_snapshot_v1`、`observation`。GET exact 按 hash 校验并只读；错误码区分 403/404/409/422，未知写结果仍由客户端冻结。
3. 前端：新增 `apps/web/src/pages/s2/AnalystMethodPage.tsx` 和最小 API client，修改 `apps/web/src/App.tsx` 增加 `/aip/analyst/methods` 子路由；在现有经营参谋或 AIP 参谋页添加非一级菜单链接。受控一次提交、固定幂等键持久化，未知结果冻结并提供 exact/Receipt 只读对账说明；不进入 offline queue。既有 `AnalystPage` 七个视图及“只读”测试不得改变。改前哈希 App 与页面开码前读回登记。
4. 后端新增路由契约测试：auth/role、错租户、空键、Hash/版本/幂等、exact read、当前库只读观测；前端新增配置页测试：字段约束、一次提交、未知冻结、无跨租户显示。先专项，再邻接/累计，构建，再当前 8080/8434 重启与浏览器验收。

## 数据、回滚、停止条件

唯一获准正例为 `org-org/dev-project` 的新方法元数据，内容必须说明仅描述观察且不证明因果；不读商城源库、不触碰旧 12 Runs。若当前身份角色不可用，先完成只读/拒绝验收，不放宽守门；若 POST 结果未知，不换键重试。当前卷不删/不重建；回滚仅停用新路由/入口并保留已写正式历史。E04 完成须有 verification、m1 commit、浏览器实际入口与 readback，之后自动 E05（Metric/Evidence/D01 产品输入择阻断最大的最小切片）。
