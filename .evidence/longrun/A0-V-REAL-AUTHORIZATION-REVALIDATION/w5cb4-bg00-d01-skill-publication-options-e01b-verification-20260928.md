# W5CB4 BG-00 E01b：技能发布页面精确候选验收（2026-09-28）

## 结论

页面不再要求用户手填 10 个 ID/修订/hash；只有从当前认证租户的只读候选中显式选定发布事件、Logic 与路由/策略，确认后才可向原发布 Owner 提交。候选不是授权，最终 POST 仍重验。当前权威库的候选为 0，因此页面按钮禁用；本波没有执行真实发布。

## 方案、测试与浏览器证据

- 上位 231/231-9 BG-00/BG-03、产品方案及本波 E01 方案复审后，专项先 RED：页面未调用当前候选 GET。实现后 `SkillPublishPage.test.tsx` 3/3，通过空候选禁入、显式三选择、单次非排队 POST 与未知结果冻结；相邻目录/模型/评测四文件累计 25/25。Web TypeScript + Vite production build 通过，只有既有大 chunk 提示。
- 复审发现旧页使用通用 `apiPost`，可能将权威发布写命令排入离线队列。本波改为 `apiPostUnqueued`；候选改为 `apiGetAuthoritative`，不使用离线缓存。发送前本地持久化单次 idempotency key，回读租户、技能与 Receipt 成功后才解除；任何不确定结果均保持禁入，不能刷新后换 key 重发。当前没有自动清除此边界的逻辑，须先权威对账。
- 浏览器打开真实 `http://127.0.0.1:8434/aip/skill-publish`：当前 37 条 evaluated、已发布 0；首项页面显示 `RELEASE_PUBLICATION_UNAVAILABLE`、`LOGIC_PUBLICATION_UNAVAILABLE`、`MODEL_ROUTE_UNAVAILABLE`，发布按钮 disabled，原十项自由输入消失。8080 当前 GET D01 返回 HTTP 200 且同样三组候选为空。

## 风险与下一波

候选的后端筛选和前端选择仅改善合法配置路径，不产生正式 Release/Logic/Route 权威，也不允许启 worker/Provider。当前 a0v_106 与代码 a0v_107 仍有迁移门，D01 联合自然首链未绿。下一波 E02 应围绕可配置的正式 Skill/Logic/Route 来源与绑定推进，先复习上位方案和现时 Owner，避免造默认值或重放旧 Run。提交后以最新代码及同一当前数据卷重启并核验服务边界。

## 提交后最新栈重启补证

E01b 提交 `43313135` 后，当前代码只读 preflight 为 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：数据库 `aos_current_preview_20260927`、a0v_106、唯一 approved installation、4 包 published、binding 0。精确停止旧 API/Vite，重启 `colima-aos-extension/aos-a0v-recovery-pg` 同一容器/命名卷且未删除数据，PG `pg_isready` 接受连接。Vite 守护自行恢复 8434，API 用最新代码安全启动，明示 `migrationMode=disabled`、workers 0、Runtime Host 0；8080 OpenAPI 与 8434 页面均 HTTP 200，18181 无监听。浏览器 reload 后短暂离线快照禁入；再次读回当前真实页面恢复 37 evaluated、0 published、三 blocker 与 disabled 按钮。重启与浏览器恢复只证明服务/禁入，不证明发布或首链。
