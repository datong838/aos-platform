# A0-V 真实文本 Provider 健康验证方案

## 1. 目标

使用上一切片建立的 `ProviderInstanceRevision:a0v-agnes-text-readonly-dev@1`，在 `org-org/dev-project` 下执行一次有界 Agnes 文本健康请求；成功后写入 15 分钟有效的 `ProviderHealthObservation`。该观察只证明执行时点的 Provider 可用，不授予 ModelRoute、Capability、AgentRun 或 A1 业务权限。

批准引用固定为 `approval:AOS-000573:A0-V-local-readonly`。请求仅含预先固定的无客户数据文本“请仅回复：健康检查通过。”，data classification 固定为 `public_catalog`。

## 2. 公共探针最小修正

现有 `AipR1BootstrapProbe` 是未注册到 Router/Adapter/Agent tool 的受限底层探针，但把历史批准 `35-R1-C` 写死。为防止 A0-V 冒用历史批准，对构造器增加可注入的 `allowed_approval_refs`，默认值仍严格保持 `{35-R1-C}`；A0-V 执行器只注入当前批准。请求合同增加 `max_output_tokens`，默认及 A0-V 固定为 32，并透传为文本 Provider 的 `max_tokens`，限制本次调用成本与响应范围。

## 3. 执行器与控制条件

新增 `scripts/a0v_real_text_provider_health.py`：

- 默认 preflight；`--apply --database-name aos_meta_head` 才可调用。
- 固定 Provider exact ref、NetworkPolicy `a0v-ecommerce-network-v1@1`、插件 `agnes-text@3`、模型 `agnes-2.5-flash` 与当前批准。
- 调用前重新验证数据库身份、Provider lifecycle/hash/Secret exact ref、network/egress/data policy、canary 为 0，且当前 Provider 尚无未过期 healthy observation。
- 最多 1 次 Provider 请求、每次最多 1 个 transport attempt、timeout 10 秒、max output tokens 32、无 fallback。
- 只输出 HTTP 合同通过后的 metadata：latency、token count、response model、answer present；禁止输出 prompt、answer、headers、Secret、response body。
- 成功后记录 15 分钟健康观察；Provider 请求失败或结果合同失败时，不写健康观察、不重试、不换 Provider。
- 若重放时 exact Provider 已有未过期 healthy observation，直接回读，Provider call=0、DB mutation=0。

## 4. 退出条件

首次成功标记 `A0V_REAL_TEXT_PROVIDER_HEALTH_GREEN`，要求 Provider call=1、健康观察 mutation=1、canary=0；有效期内重放要求 Provider call=0、mutation=0、观察 exact ref 不变。随后总依赖审计首门应推进到 `modelRoutes`。

如果端点、凭据、模型、响应合同、token metadata 或时限有任何异常，标记 `SAFE_BLOCKED` 并记录稳定 reason code。网络结果未知时不得自动重试；后续只能先读取 Provider 侧或持久 Receipt 进行人工判定。本切片不使用 Prime OAuth，不产生电商业务 mutation，不执行 230 L0。
