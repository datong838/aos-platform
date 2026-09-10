# AR2-7E Prime 最终增量只读复核

日期：2026-09-10

审查目标：`aos-platform/m1@e52ec81a`

Prime provider：`github-copilot`

Prime model：`gpt-4.1`（隔离配置固定为 `openai-completions`）

结论：`VERDICT: PASS`

## 1. 执行边界

- Prime 使用 `--no-tools --no-session --no-context-files --no-extensions --no-skills --no-prompt-templates`，只读取累计方案、机器结果、清册、两套总矩阵验证和八个富交互专项验证。
- 隔离配置目录由 `PRIME_AGENT_CODING_AGENT_DIR=/tmp/prime-ar2-review-20260910` 指定；OAuth 凭据由 Prime 本地 AuthStorage 读取，未进入命令输出、审查输入、AOS 仓库或证据正文。
- Prime 不写业务代码、证据、authority 或并行分支；本次模型调用是开发期只读审查，不是 AOS 业务 Provider 调用。
- 真实业务 mutation、费用、发布、生产/共享迁移、push 和 `230 L0` 均保持关闭。

## 2. 独立结论

Prime 首行原文：

> VERDICT: PASS

Prime 确认：

1. 入口与反向矩阵 37/37 PASS；有效隔离数据矩阵 24/24 PASS，24 张截图可回读。
2. Task Cockpit、Content Campaign、Operations、Creator Growth、Media Studio、Analyst、Price Governance、Customer 八个富交互专项各 3/3 PASS。
3. 请求、租户、页面、控制台错误与禁止副作用计数为零；各专项 `zeroEffects` 与累计边界一致。
4. 使用合同 fixture 与隔离研发链路，没有真实客户/经营数据、真实业务 mutation、AOS Provider、费用或外部发布。
5. Prime OAuth 只作本地开发辅助，没有成为 AOS 产品或验收运行依赖。
6. 最终标记只可闭合 AR2-7E，不得冒充 A0-V、真实八场景、230 L0 或生产发布完成。

## 3. 调用纠偏留痕

首次调用误用了无效环境变量 `PRIME_CONFIG_DIR`，CLI 因而忽略隔离 `models.json`，内置 Responses API 模型被 GitHub 返回 400。修正为源码规定的 `PRIME_AGENT_CODING_AGENT_DIR` 后，单句探针输出 `PRIME_MODEL_PROBE_OK`，正式复核成功。失败调用未产生审查结论、未修改仓库，也未被计为 PASS。

## 4. 退出判断

Prime 最终增量只读门 PASS。AR2-7E 已具备进入本地 closure 全量复跑与最终 Delivery Receipt/CAS 的条件；本文件本身不前推 authority。
