# A0-V 真实文本 Provider 权威实施方案

## 1. 目标与阶段边界

本切片只为 `org-org/dev-project` 建立一个可由 AOS 精确解析的 Agnes 文本 `ProviderInstanceRevision`，并证明其 Secret、插件、端点、egress、data-classification 与 network 前置条件可用。它不创建模型或路由，不启动 AgentRun，不执行电商业务任务，也不把 Provider 建立等同于 A0-V GREEN。

本切片沿用 `AOS-000573 / A0_V_REAL_AUTHORIZATION_REVALIDATION`，批准引用固定为 `approval:AOS-000573:A0-V-local-readonly`。Prime 的 GitHub Copilot OAuth 和 `~/.prime/agent/auth.json` 不属于 AOS Provider、Secret 或产品运行时权威，禁止读取、复制或引用。

## 2. 已复核的产品与技术约束

- 首链最终验收单位仍是“自然槽位 → Case/Run → 真实只读数据 → 分析建议 → exact 评审 → 内部内容任务 → capability/预算门 → Artifact → 人工评审自动续跑 → 总控复盘/Wiki 候选”。本切片仅关闭其中的 Provider 静态准入前置。
- A0-V 不执行 A1 真实业务链；Provider 健康观察必须独立、短期有效，不能由静态配置、历史记录或 Prime 登录替代。
- 只允许正租户 `org-org/dev-project`；`dev-org/dev-project` 是负向隔离 canary，写入数必须保持 0。
- 使用已发布的 `a0v-ecommerce-egress-v1@1`、`a0v-ecommerce-public-catalog-v1@1` 与 `a0v-ecommerce-network-v1@1`，禁止复制出第二套宽松策略。
- Provider 插件必须是文件权威 `ProviderPluginRevision:agnes-text@3` 的精确 hash，模型必须是插件批准的 `agnes-2.5-flash`，端点必须是 `https://api.agnes-ai.cn/v1`。

## 3. 最小实现

新增 `scripts/a0v_real_text_provider_authority.py`，默认只做 preflight，`--apply` 才允许写入。脚本复用当前隔离恢复库连接与备份实现，并固定以下对象：

- Provider ID：`a0v-agnes-text-readonly-dev`
- revision：`1`
- lifecycle：`active`
- Secret ref：`keychain://com.aos.llm/agnes-text/org-org/dev-project/a0v-agnes-text-readonly-dev#api-key`
- Secret version：`a0v-v1`
- endpoint：`https://api.agnes-ai.cn/v1`，region 与现行 egress 完全一致，timeout 10 秒

产品数据库只保存 Secret ref/version，不保存 Secret 内容。脚本仅从仓库根目录 `.env` 的 `AGNES_API_KEY` 读取非空值，使用私有伪终端调用 `/usr/bin/security add-generic-password ... -w`：Secret 只写入已关闭 ECHO 的终端输入，不进入 argv、环境或输出；标准输出、错误和证据均不得包含 Secret。这样条目创建者与现有 `/usr/bin/security` resolver 一致。已有非空条目不覆盖；不可判定条目默认 fail closed。仅在 `--repair-keychain-item` 显式模式下，针对本阶段已由 v1 `secret_keychain_empty` 故障证据确认的精确 service/account，先删除旧条目再由同一 `/usr/bin/security` 进程重建，避免保留首次错误写入产生的 ACL。若 `.env` 的 base URL 或 text model 与固定批准值不一致则 fail closed。

## 4. 执行顺序与退出条件

1. preflight：确认目标数据库、插件、三项 exact policy、`.env` 三个必要字段与 Keychain 状态，仅输出存在性和非敏感 identity。
2. 建立独立 pre-mutation 数据库备份。
3. 若需，写入精确 Keychain 条目；随后用 `ExactSecretResolver.probe()` 只验证存在性。
4. 通过生产 `AipModelRuntimeStore.publish_provider()` 发布 Provider，回读 exact ref。
5. 重放同一命令，要求数据库 mutation=0、Keychain mutation=0、exact ref 不变。
6. 校验 canary Provider/health 均为 0，且本切片 Provider 调用数、业务写入数、外部发布数均为 0。

退出标记固定为 `A0V_REAL_TEXT_PROVIDER_AUTHORITY_GREEN`。任何数据库身份漂移、已有 Keychain 条目无法探测、插件/策略/hash/端点/模型漂移、Provider head 冲突或 canary 非空，均 `SAFE_BLOCKED`，不尝试替代后端、不覆盖既有 Secret、不继续外部调用。

## 5. 后续门与风险

下一切片才使用该 exact Provider、当前 network policy 和固定开发样本执行有界健康探针，最多一次尝试，不记录 prompt、answer、headers 或 Secret；成功后写入短期 `ProviderHealthObservation`。健康门通过后再建立价格、模型、Eval gate 与 ModelRoute。

主要剩余风险是本机登录 Keychain 可访问性与 Agnes 端点的实时状态。Provider 配置成功只能证明静态权威闭合，不能证明服务健康、模型路由可用或首链业务成功。
