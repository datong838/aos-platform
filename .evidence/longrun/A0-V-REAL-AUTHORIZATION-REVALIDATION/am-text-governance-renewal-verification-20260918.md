# AM 文本治理续签验证（2026-09-18）

## Rules

- 复用已评审的 `text-readiness-v2` 固定三案例，只使用公开合成输入。
- 每案例最多一次 Provider 调用；先持久化 intent，失败或未知结果不得更换 key 重发。
- 探针不读取商城正文、不修改业务 Run；正式续签只走既有 Owner 和 head CAS。
- 本结果只恢复有限时间的模型治理授权，不等同于 AM 安装、AL 退休或真实经营闭环完成。

## 第 1/6 步：独立批次

使用全新私有 journal `../.aos-recovery-20260918/state/am-text-readiness-v2`。preflight 固定 `instruction/source/missing` 三案例，Provider 调用数为 0。

## 第 2/6 步：真实探针

三案例均一次完成，`status=healthy` 且 `response_contract_passed=true`：

- instruction：73/4/77 tokens，528ms；
- source：77/3/80 tokens，993ms；
- missing：81/3/84 tokens，701ms。

总计三次 Provider 调用，业务变更数为 0；未出现失败、未知结果或重发。

## 第 3/6 步：冻结续签计划

正式 Owner 从上述 evidence 冻结计划：

- plan hash：`9f742a2220a471b248c383be23748036f5d2a15cf02a979a72cbc52aaeefbf37`
- source hash：`92bfe309c5bb29011e0ff9bb943a0f890ed7cace2a9b5ce600476ba0b62768b2`
- budget expected version：7；runtime policy expected version：7；price/model/route expected version：6。
- 新有效窗：`2026-09-18T11:49:10.498230Z` 至 `2026-09-19T11:48:51.753918Z`。

冻结阶段 `providerCalls=0`、`databaseWrites=0`。

## 第 4/6 步：正式发布

沿原正式 CAS 发布链完成：budget rev8、runtime policy rev8、price rev7、model rev7、route rev7。模型 Gate 为 `gate-c0cc83a8ceb040584aa4cd677bca3fde`，路由 Gate 为 `gate-0bbdb8bda87f08390244003f0efcb759`。发布阶段 `providerCalls=0`、`businessRuns=0`。

## 第 5/6 步：边界复审

续签未触碰 AL definition rev51 disabled、十二 Run、保存输入、relationship/link command 或 Store；`readiness=NOT_CHECKED` 明确表示这一步未声明 AM 运行时已就绪。

## 第 6/6 步：下一波

下一波直接执行 AL 正式 disable Owner 的 fence/detach，只在九路 legacy、binding disabled/fenced、三资源 released、零 unresolved/pending/canary 与唯一 detach Receipt 同时成立后建立 AM direct successor；随后重新 stage/configure/enable 并迁移保存输入。
