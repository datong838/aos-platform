# SC4-5L6Z U 九路 successor 登记与切换方案

日期：2026-09-17  
基线：`0b031844`，分支 `m1`，单写者，不 push，230 L0 保持挂起。

## 当前权威

U installation `277fe01c-ece7-4c8f-9500-fc1ba0d5f050` 为
`active@5 / binding revision4 / epoch3 / enabled / ready / unfenced`，generation
`f576ea28-7c2b-4032-8b4c-9d196df6228e`，config
`7b0bfd0f-c1ca-474b-be32-de0cf47e5308@1`。三资源 pending/unreleased，四项 lifecycle operation
均成功，唯一 Host crash-rehydrate 后持续续租，canary0。

S 已 `uninstalled@6`。其正式 disable operation
`5243452a-161c-40cb-aa9c-6dc5dd8f544b` 的最终 detach Receipt 为
`f32084bb-b1b5-482c-8b4f-9a28f414ce61@sha256:7d9842222015f2e18408c50f95c3dc5ee8a70460de92ec478822e7c19bbaa1de`。
九条路由均为 `legacy / fenced / routeRevision35 / groupRevision62`，无 running execution、无
claimed/unknown occurrence dispatch、全租户无未决 runtime operation。

## 第 1/6：固定 successor registration

新增 `scripts/a0v_u_successor_business.py`。只接受上述 U、S detach Receipt、九路 group62 和零在途；
使用 `aos.ecommerce.successor-dispatch-registration/v1`，expectedGroupRevision=62，注册目标固定为
U binding revision4/epoch3/config。使用全新 key `a0v-qyh-clean-generation-u-successor-v1`。
preview 只读；register 冻结 intent/result，存在 intent 时只读原 Receipt，禁止重发。

## 第 2/6：固定切换

新增 `scripts/a0v_u_successor_cutover.py`。切换 operation 固定为
`8cfc486b-254b-58ce-8211-eac0ec015244`，prefix
`a0v-qyh-clean-generation-u-cutover-v1`；只使用 U registration Receipt 和新 RuntimeCutoverPolicy。
严格执行 approve → prepare → pause → commit → validate → resume。每阶段先冻结独立 intent/result；
任何已有 intent 都要求 inspect，不重发。externalEffectsAllowed=false、fallbackAllowed=false。

## 第 3/6：终态验证

新增 `scripts/a0v_u_successor_cutover_verify.py`：要求 U binding revision6/epoch3、九路全部
`extension / U / epoch3 / unfenced / routeRevision36 / groupRevision63`，切换历史为 resumed 且五类
Receipt 完整；S/T 均 uninstalled/released，唯一 Host live target 为 U，canary0、零在途。验证只读，
结果写独立 JSON 证据。

## 第 4/6：测试与闭包

新增三份 fixed-executor 测试，覆盖常量、U/S/route/Receipt 漂移拒绝、阶段顺序、旧 intent 禁止重发和
终态拒绝。回归原 successor/cutover 服务测试，执行 AR2-7 闭包与 `git diff --check`。

## 第 5/6：真实执行

先 preview，再 register；随后逐阶段执行切换并在每阶段读取 Receipt/history。任一未知结果停止写入，
只读 history。切换过程不启用 snapshot definition、ProductEvent Policy 或经营参谋 schedule。

## 第 6/6：下一波

切换 GREEN 后提交证据并自动进入 P01-P12 新代权威：为 U 重新签发 selection/control/binding，配置全新
disabled definition，验证关系策略后短时 enable 让 worker 自然生成完整组，再立即 disable。不得复制 S
的 control、claim、run 或 occurrence。
