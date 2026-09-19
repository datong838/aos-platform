# AU 陈旧健康实例正式退休方案

## 当前边界

AU installation `eddc89f9-1e91-4e42-be4e-7d81dc941c1d` / generation
`01a5eb0a-f41f-40f7-ba00-b5db23a7806f` 已完成 successor cutover，九路为 extension rev114/group141；
随后因 runtime-apply Health observation 过期，被正式 owner 推进为 Binding rev7/epoch4、disabled/fenced、
desired enabled、observed unknown，三资源均 released。

definition 保持 rev73 disabled，AU attempt=0，全租户 running/unresolved/runtime pending=0，canary=0。该状态是安全冻结
边界，但不是正式 disable/detach，不能直接创建 AV，也不能在 AU 内重新 enable。

## 文件级清单

1. `scripts/a0v_au_stale_health_guard.py`：只读锁定 AU identity、Binding rev7/epoch4、九路 rev114/group141、
   三资源 released、definition rev73 disabled、attempt=0、零 in-flight/canary；只输出分类，不写数据库。
2. `scripts/a0v_au_stale_health_retirement.py`：复用正式 RuntimeDisable Owner，唯一请求 expected binding rev7；先读回
   accepted/terminal，再由 consumer 完成 fence/detach；immutable intent 已存在时只读核账，禁止再次提交。
3. 对应专项测试：锁定 exact identity/revision、零 attempt、禁止 `run_definition`、禁止直接更新 route/binding。
4. verification：记录唯一 disable operation、fence/detach Receipt、legacy 新 revision/group、definition 与零副作用边界。

## 串行步骤与停止条件

1. guard 必须返回 `AU_STALE_HEALTH_RETIREMENT_REQUIRED`；任一 identity、route、definition、attempt、in-flight 或
   canary 漂移立即停止。
2. request-disable 只允许一次，expected binding revision=7；若结果未知，只读查 operation/receipt，不重发。
3. process-disable 只处理该唯一 operation 的正式 outbox delivery；终态必须 succeeded/acknowledged。
4. audit 必须证明 Binding rev9/epoch5 disabled/fenced/observed unknown、3/3 resources released、九路 legacy
   rev116/group143、definition rev73 disabled、attempt=0、零 in-flight/canary，且 lifecycle 恰为 fence/detach。
5. 专项/累计测试、编译、差异检查、8434 只读复验、verification 与 commit 完成后，下一波才可从 exact detach
   Receipt 创建 AV。

不读取商城源数据，不调用 `run_definition`，不修改十二 Run/Dataset Receipt，不 push，230 L0 保持挂起。
