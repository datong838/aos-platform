# 本人在 Web 办理 cost 父链（助手不代 POST）

**正确入口（不是「运行就绪」）：**

- **URL：** [http://127.0.0.1:18434/aip/capacity](http://127.0.0.1:18434/aip/capacity)
- **侧栏：** **模型管理 → 容量管理**
- **页内位置：** 进入后**在页面最上方**（在「用量 / 限速」Tab 之上）依次有预算相关卡片，其中一张标题为 **「费用风险审核与恢复」**（`aria-label` 同名）。

**易错：** [http://127.0.0.1:18434/aip/model-runtime](http://127.0.0.1:18434/aip/model-runtime)（运行就绪）只有 **「成本与预算权威」** 只读汇总，**没有**费用提议办理 UI。

**租户：** org-org / dev-project

**开发登录：** Vite 开发模式默认跳过登录页；OIDC 仍用于 API。若无会话，页顶黄条会提示；或临时 `VITE_AOS_SKIP_LOGIN_GATE=0` 登录一次后改回。

## 顺序

0. **费用提议发起（3 个月开发默认）** — 同页卡片：额度 100/1000 元·日/月、滚动 **3 个月**有效窗（**非**正式续期截止）；须权威预算候选覆盖满 3 个月。预填 agnes-2.5-flash / 10·100·100 风险；选**不同于你的**审核人 → 发起（maker）。
1. **独立复核费用提议（decide）** — 须 **checker 账号**登录；提议 ID 会在发起后自动填入下方表单 → **读取费用提议** → 批准。
2. **启用已批准预算（consume）** — decide 批准且未过期后。
3. **生成费用配置（configure）** — consume 回执 observed 后。
4. **unknown/unresolved：** 同提议 ID，点 **「查询费用原请求」**，禁止重复 POST。

## 办理后

把 **proposalId**（可打码）告诉助手，用于只读对账；**不要**发密码或 Token。

## 对照材料

- `cost-parent-review-material.md`
- `paired-window-review-material.md`（cost 完成后才办 window）
