# P6C-B · 用量归因与版本化限额验收记录

## 结论

- 状态：`CODE_TEST_BROWSER_GREEN`。
- 范围：`AIP-P6-106`、`AIP-P6-107`。
- 边界：未调用 Provider，未回放历史任务，未修改真实经营数据，未自动切换模型路由/配额绑定，未发布。

## 专项与累计回归

- 后端：归因 authority、模型治理合同/store/API 与模型运行合同/API 共 `53 passed`。
- 中断恢复后新鲜复跑：本子包两组核心后端文件 `22 passed`（耗时 7m54s），与上述累计口径无冲突。
- 前端：runtime parser、CapacityPage 与 W3B 负向交互共 `57 passed`。
- 中断恢复后新鲜复跑：同一三组前端文件仍为 `57 passed`；仅保留 React Router v7 未来行为提示，无本子包错误。
- TypeScript：`tsc -p tsconfig.json --noEmit` 通过。
- 生产构建：`vite build` 通过；既有 bundle 大小提示不影响本子包正确性。
- 静态检查：`git diff --check` 通过。

## 真实租户浏览器验收

- 租户：`org-org/dev-project`，页面组织显示“栖月汇商贸有限公司”。
- 页面：`/aip/capacity`。
- 近 30 天权威用量：16 条 Usage Receipt；2,928 个 Token 用量单位；实测 16、估算 0、未知 0。
- 五维归因：
  - 租户：栖月汇微商城 16 条；
  - 经营任务：16 条，由 Receipt lineage → canonical TaskRun 解析；
  - 数字同事、业务逻辑、模型：各明确显示“16 条暂无归因凭证”，没有把缺证伪装为业务零。
- 版本化配额：读取 `quota-qyh-text-dev@1` head；RPM/TPM 输入组件可编辑，填写 `120/240000` 后“保存新版本”按钮可用。本次未点击保存，因此真实租户没有策略写入。
- 浏览器控制台：未发现本子包新增的错误；已消除 tab 按钮 border shorthand/longhand 冲突警告。

## 隔离 canary CAS 验收

- 范围：`dev-org/dev-project`，仅用于开发隔离验证。
- 创建：`quota-p6c-browser-20260901-01@1`，RPM 120、TPM 240000，HTTP 201。
- 精确回读：revision 1 与 content hash `a6ccda71d6b156490c85211e60ae6024c1921cd751fbe2225e17b29a30ef11da` 一致。
- 冲突：用过期 `If-Match: 0` 创建 revision 2 返回 HTTP 409 / `AIP_MODEL_GOVERNANCE_POLICY_VERSION_CONFLICT`。

## 证据

- `p6c-b-usage-attribution.png`
- `p6c-b-versioned-quota.png`
- `p6c-b-plan.md`

## 方案一致性复核

- 用量数量仍只认 Usage Receipt/Adjustment；没有建立第二套用量权威。
- task 只经 lineage 解析；Agent/Logic/model 只认显式 UsageAttribution，缺证不猜测。
- RPM/TPM 以成对可空字段扩展旧 QuotaPolicyRevision，旧 revision 兼容回读；新 revision 继续走 Idempotency-Key + If-Match CAS。
- 页面保存只创建新 revision，不把“创建完成”冒充“运行绑定已生效”。
