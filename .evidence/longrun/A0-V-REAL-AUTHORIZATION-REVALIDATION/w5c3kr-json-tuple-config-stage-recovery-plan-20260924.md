# W5c3kR JSON/tuple 配置 Stage 恢复方案（2026-09-24）

## 原因与边界

W5c3k `3b290db4` 在原 `append_configuration` 前因冻结 JSON 数组与严格 tuple 模型不兼容而停，旧 0600 intent 存在但配置/新 key 记录均0，Host/Job/业务状态未变。本波不重用旧 state/key，修复唯一 JSON→模型恢复点，保持 append 原代码和 DB 权限不变。

## 串行步骤

1. 把 W5c3k `ConfigurationDocument.model_validate(before["document"])` 改为 `model_validate_json(json.dumps(...))`；增加定向回归测试保证角色/数据 ref 仍为严格 tuple，不能弱化验证。旧 W5c3k state/key 永久冻结。
2. 新脚本 `scripts/a0v_w5c3kr_config_stage_recovery.py` 用独立 0600 state `20260924-w5c3kr-config-stage`、新键 `a0v-w5c3kr-json-tuple-stage-20260924-v1`，先只读核旧 key0、新 key0、当前配置0、同 PID Job/三 held 资源与四来源/九路/调度/canary/预算；原 append 单次提交。
3. 独立 audit rev1/contentHash/四来源 payload、Host/绑定/lease/业务计数不变；verification 和 m1 commit。下一波才 configure。

## 停止条件

任何配置已存在、旧 key 出现写入、Host/资源/预算/九路/调度漂移、提交边界未知，冻结，不重发。
