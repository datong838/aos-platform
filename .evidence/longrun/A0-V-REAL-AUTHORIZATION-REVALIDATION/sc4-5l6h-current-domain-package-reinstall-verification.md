# SC4-5l6h 当前代际电商领域包完整生命周期验证

日期：2026-09-15
方案提交：`8f889eef`
最终代码提交：`b9546f37`
任务权威：`A0V-CURRENT-ECOMMERCE-PACKAGE-REINSTALL-20260915`，owner=`m1`

## Rules 与验收边界

- 按方案先行、m1 单写、逐阶段 Receipt、未知结果不重发执行；不 push，230 L0 挂起。
- 构建、签名、Registry、安装、配置、启停、卸载和恢复均走既有 Owner/Host；没有直接更新 installation、binding、resource、operation、dispatch 或业务表。
- 正租户固定为 `org-org/dev-project`；`dev-org/dev-project` 仅作零安装、零路由、零业务写的隔离金丝雀。
- 本波退出条件是“当前签名组合可安装、可配置、可禁入、可恢复、可卸载重装并由真实 Host 承载”。它不把 qualification fixture、API 页面可读或安装成功写成栖月汇真实经营首链成功。

## 当前组合的构建、资格审查与签名

- 构建结果 `BUILD_GREEN`，输出树 `sha256:5eb3eaa7a32de3fc3e46d46a16cfc3ba1e322d75337a92823eb54b6980bcbd10`，唯一解析为 core 1.3.0、Niushop 1.22.0、growth 1.8.0、operations-base 1.2.0。
- 资格审查结果 `QUALIFICATION_GREEN`：三个 Runtime 成员均完成 exact registration、各 2048 次 heartbeat、贡献数分别为 1/2/24，随后资源 released；growth 只读 probe 明确标记 `qualification-fixture-only / executionAllowed=false`。
- image index bytes、image digest、dependency lock、SBOM、backend、schema compatibility 与 schema requirements 七类篡改均被拒绝。资格审查期间 Provider、Registry、安装及外部发布副作用均为 0。
- 永久签名后继根保留父根 14 个版本的原字节，只新增 Niushop 1.22 并形成 15 版本目录。Registry 发布结果 `CURRENT_ECOMMERCE_REGISTRY_GREEN`：只对 Niushop 1.22 与 growth 1.8 各执行 create/publish/validate，共 6 次 Registry mutation；安装数仍为 9，canary 为 0。主库前置备份为 5,472,696 字节，哈希 `sha256:b92a75664ee4c0160023afbdf72096cbaacc9821c4cea0383b827503723dabe5`。
- 受控文本模型续期使用固定 3 个公开文本用例，一次通过 `FIXED_TEXT_CASES_PASSED`；正式续期只写模型/路由治理资产，得到 model revision 4、route revision 4，apply 阶段 `providerCalls=0 / businessRuns=0`。

仓外只读证据：

- 构建：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/build/build-receipt.json`，SHA-256 `4cca13ebbf3a44a34cf3e4341ba61a9b5745adeaf502221e1f593d1d9f05e0fb`。
- 资格审查：同目录 `qualification-receipt.json`，SHA-256 `d2bf463c6b2201e5088335819b65be1d2de1b3d469076eb8b5de0589c9c4e7a6`。
- Registry：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/registry/apply.json`，SHA-256 `1494db8b7a49bb311d539f2297f9d0ffea9a9cfab9e48a0c07b5bf72fbeeccc2`。

## 失败安全、恢复与叶子优先卸载

1. 安装 A `cbbb55d6-9063-47ef-aeba-869973a54df4` 完成 approve/prepare/verify/configure。首次 enable 被 replacement guard 安全拦截：前驱缺少当前 `disabled_committed`，Host 没有越过门禁；随后原 Receipt 过期，控制器经正常 disable 路径取消，而没有重发未知 enable。
2. A 的第二个恢复 enable 虽被接受，但三项 Runtime 资源已 released，目录中没有 runtime-apply 进程 Owner。控制器再次经正式 disable 取消该未执行操作，没有把“数据库状态可改”冒充“运行资源已恢复”。
3. 安装 B `c9f51df5-8b09-40b7-bd64-f8d92ac7e22b` 以 A 的精确 revision/lock/overlay 为前驱，完整执行 runtime-apply/verify/configure/enable 并达到 ready/enabled/unfenced，证明 released 场景必须以 replacement reinstall 恢复。
4. B 活动时直接卸载 A 被既有 replacement lineage guard 拒绝且事务回滚。按叶子优先顺序先 disable/uninstall B，再复用已冻结的 A uninstall intent 卸载 A；A、B 最终均为 `uninstalled@6 / stopped / fenced`，全部资源 released。
5. 最终安装 C `044c2743-9700-4e84-a6c1-98670c94f005` 从最初已排空前驱重新走完整生命周期：active@5，lock `sha256:4c7010d1b5758e93c598d169515d61cd94c7b33ceb0f1d2e729a265a63384db3`；generation `09d2a19a-d85a-4c81-981c-87c1600944ea` 为 revision 4 / epoch 3 / enabled / ready / unfenced，三项资源均由当前 Host 持有，canary installation 为 0。

最终安装观察文件为 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/install/observe-after-enable-c.json`，SHA-256 `b36a033679190b6b5d53b2dd227c05a6620602bf2fcb58a6d28f4c66f041d823`。

## 服务、目录与主库独立读回

- 唯一 Runtime Host 使用本波 15 版本签名根，最终 C 下三个 OCI 成员保持 running；受控 API 同样显式使用该根，且 migration、内嵌 Runtime Host、QYH Cron、AIP Logic automation、模型维护和 SSH 预热均关闭。
- `GET /v1/health` 为 200；5173 与 8434 的 `/ontology` 均为 200。缺 Bearer 的 Runtime Workshop 目录为 401；使用现有开发 Bearer 与正租户 header 后为 200，只返回一个 `ecommerce.analyst`，其 installation、generation、binding revision、growth 1.8 package hash 与最终 C 精确一致。
- 主库仍为唯一 head `a0v_050`。相对升级前 34 类关键表指纹，只有 bundle installation/revision 与 Runtime configuration/binding/operation/resource lease 六类预期生命周期表变化；其余 28 类来源、管道、商城对象、Task/Run、Case、Outbox、Fulfillment 与领域 Receipt 表指纹保持不变。
- 当前正租户共有 11 个历史 binding，仅最终 C 的一个 binding 可执行；未停 schedule=0、claimed/unknown Outbox=0、dispatch=9。canary dispatch=0、业务写=0。本波没有创建经营 Run，也没有读取上游商城。
- 独立读回：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/final-readback.json`，结果 `CURRENT_ECOMMERCE_PACKAGE_FINAL_READBACK_GREEN`。

## 回归、闭包与记忆一致性

- 当前 builder、签名后继、重装控制器与 API 根切换：`32 passed`。
- PostgreSQL disable/replacement guard/租约/围栏：`27 passed`，显式启用独立数据库测试，无 skip。
- AR2 `verify_closure.py --phase ar2-7`：1956 scanned / 196 classified / 93 migrated；hash、前向、反向、跨层与动态引用错误数组均为空。
- `memory-validate`：GREEN，AOS-000573，1201 Delivery / 1185 Task / 2902 Event。七个 strong projection 均 CURRENT；Codex eventual projection 仍为 PENDING_ASYNC，不手工提升。
- `git diff --check` 通过。用户已有 `overall-progress-20260913.md`、`package.json`、`package-lock.json` 差异未触碰。

## 结论、限制与下一波

`CURRENT_ECOMMERCE_PACKAGE_REINSTALL_GREEN`：当前领域组合已经用真实主库、真实安装 Owner、真实 Runtime Host 与真实隔离容器证明可安装、配置、禁入、失败恢复、叶子优先卸载并再次重装；当前 API 和 Runtime Workshop 目录也已切到最终 C 的签名资产。

尚未形成发布结论。下一波固定进入栖月汇真实 Source 与经营计划：先独立重验当前来源授权、SSH/JDBC/十二源映射和数据截止时间，再让经营参谋基于真实事实产生有来源的计划候选；随后由真实 ProductEvent 自然创建 Case/Run，继续验证 exact 阶段评审、内容任务、能力/预算/审批、产物、人工评审后续跑、总控复盘与 Wiki 候选。任何质量不足、来源漂移或权限失效都保留为阻断，不用 fixture 或手工接线补绿。
