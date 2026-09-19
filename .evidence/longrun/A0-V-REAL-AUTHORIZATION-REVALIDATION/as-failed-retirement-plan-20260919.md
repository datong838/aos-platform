# AS 失败实例正式退休方案

## 当前权威

AS installation `5d0a6d5a-4024-430f-831b-2af15b5ca889`、generation
`4cc2dc84-a452-4bac-aa56-0b1519a9826a`，安装 etag5，Binding rev6/epoch3
`enabled/unfenced/ready`，九路 extension rev108/group135，三资源未释放。唯一 attempt
`af7c1fc1-8283-40d7-ab62-f7d6145417c6` 已 failed rev5，definition 已暂停为 rev70 disabled；十二 Run 与
Dataset Receipt 保留，Store 与投影副作用为零。

## 文件级清单与动作

1. 新增 `scripts/a0v_as_failed_retirement.py`，固定 AS 身份、锁摘要、唯一失败 attempt、definition rev70、
   路由和冻结业务边界；只允许 `preflight → request-disable → process-disable → audit`。
2. 新增 `services/aos-api/tests/extension_runtime/test_a0v_as_failed_retirement.py`，锁定单次 disable 交付、
   禁止 `run_definition`、不修改十二 Run。
3. `request-disable` 仅经既有安装控制 Owner 申请；`process-disable` 先读回，未知结果不得重发；仅在 exact
   accepted 状态调用一次正式 consumer。
4. 终态要求 Binding rev8/epoch4 disabled/fenced/unknown、九路 legacy rev110/group137、三资源 released、
   definition rev70 disabled、唯一失败 attempt 不变、无 running/unknown/runtime pending、canary0。

## 退出条件

专项测试与累计回归通过，四阶段结果均以 0600 私有文件冻结，浏览器保持只读无写操作，证据与代码提交。
随后从 AS exact detach Receipt 创建 AT direct successor；不复用 AS 代次，不重发 Store，不 push，230 L0 挂起。
