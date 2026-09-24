# W5c3kR JSON/tuple 配置 Stage 恢复验证（2026-09-24）

## 结论

**GREEN，仅配置 Stage。** 原严格 `ConfigurationDocument` 从冻结 JSON 使用 `model_validate_json` 恢复，roleRefs/dataRefs 仍为 tuple；W5c3k 旧 intent/key 永久冻结、旧 key 配置0。新键 `a0v-w5c3kr-json-tuple-stage-20260924-v1` 仅一次经原 `append_configuration(previous_ref=None)` 写出唯一配置 `f8d1f58f-9a49-48e2-b1a4-262e22f929f0` rev1/hash `sha256:f21169b03b4aba5dec2e6bbaa8ee8921e5ed833eee558f051b6e564aa068e359`，四来源 Policy rev13。

## 独立验证

- 方案 `6090d41b`；新独立 0600 intent/result。回读同安装/generation 配置仅1条、previous_hash null、持久化 payload 与冻结四来源精确一致、stage key仅1；旧 key0。
- 安装仍 active/etag5、binding rev1/epoch1 disabled/fenced/ready，Host PID17302 同真实 Job、三资源 held、九路 legacy/fenced、12 schedule off、attempt/canary0。受控源 claim40、meta_schedule_run53 不变。
- 严格 JSON tuple 回归与包装测试 3 passed，配置 stage contracts 既有 31 passed，`git diff --check` 通过。未读商城源、未发 configure/enable、未触发业务 Run。

## 下一波 W5c3l

先方案，用原 RuntimeConfigurationService 对精确 configRef/etag5/binding rev1/generation 提交一次 `configure`，自然 Host 消费至正式终态；成功必须 binding disabled/fenced、configRef 精确、Job/资源仍 held。之后才单独 enable。
