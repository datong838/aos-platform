# W5c3k 当前四来源配置仅 Stage 方案（2026-09-24）

## 前提与范围

W5c3j `68efbd78` 安装 `407059df-6f1f-4927-acd7-8e388692838e` active/etag5，generation `7571af17-e2bb-4437-9f04-75812bae56c0` binding rev1/epoch1 disabled/fenced/ready、config_ref null，三资源 held、Host PID17302 真实 Job。九路 legacy/fenced、12 schedule off、canary0。原 `append_configuration(previous_ref=None)` 支持新安装配置 rev1；W4 `_document()` 可从当前精确四来源构造 Policy/Budget/Data/Role ref。本波**仅 stage**，不发 configure/enable，不读商城源。

## 串行步骤

1. 只读再核安装/Host/lease/operation terminal/binding、九路/调度/attempt/canary、当前四来源 ref/预算有效、同安装 config0、新 stage key0。
2. 新增 `scripts/a0v_w5c3k_current_config_stage.py` 与定向测试；使用原 `append_configuration` 和 CurrentConfigurationPermission/authorize，`previous_ref=None`、etag5/binding rev1 CAS、全新键 `a0v-w5c3k-current-four-source-stage-20260924-v1`，0600 intent/result，单次事务；写前确认文档 policy rev13 且其他 ref 当前。
3. 独立读回配置唯一 rev1/contentHash/四来源 ref、installation/binding/Host/资源不变，九路/调度/canary/业务计数不变；verification 后 m1 commit。下一波才原 RuntimeConfigurationService 的 configure 单次自然消费。

## 停止条件

资源不 held、Host/Job 漂移、budget/四来源不当前、config/key 已占用、原授权拒绝、提交边界未知、任何调度或路由打开，即冻结且不重发。
