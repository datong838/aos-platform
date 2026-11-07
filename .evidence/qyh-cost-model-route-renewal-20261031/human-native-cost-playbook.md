# 本人在 Web 办理 cost 父链（助手不代 POST）

**正确入口（不是「运行就绪」）：**

- **URL：** [http://127.0.0.1:18434/aip/capacity](http://127.0.0.1:18434/aip/capacity)
- **侧栏：** **模型管理 → 容量管理**
- **页内位置：** 进入后**在页面最上方**（在「用量 / 限速」Tab 之上）依次有预算相关卡片，其中一张标题为 **「费用风险审核与恢复」**（`aria-label` 同名）。

**易错：** [http://127.0.0.1:18434/aip/model-runtime](http://127.0.0.1:18434/aip/model-runtime)（运行就绪）只有 **「成本与预算权威」** 只读汇总，**没有**费用提议办理 UI。

**租户：** org-org / dev-project

**开发登录：** Vite 开发模式默认跳过登录页；OIDC 仍用于 API。若无会话，页顶黄条会提示；或临时 `VITE_AOS_SKIP_LOGIN_GATE=0` 登录一次后改回。

**顶栏「aos-api 不可达 / 无法连接 /api」：** 多半是 **18434 Web 掉线**（API 本机仍可能在 18080/8080）。依次执行：

1. `bash .evidence/qyh-cost-model-route-renewal-20261031/private/maintain-web-18434-restart.sh`
2. 仍失败：`bash scripts/demo/ensure-api.sh`，浏览器顶栏 **API Base 改回 `/api`** 或清站点数据里的 `aos-api-base-v1`
3. 日志：`deploy/dev/aos-api.*.log` · Web：`.evidence/.../private/web-18434-restart.log`

## 顺序（您 mostly 只点「确认」）

0. （若提示候选截止不等于 **2027-03-31 12:00 北京时间**）页顶 **确认写入 draft（推荐默认）**。
1. **确认发起（推荐默认已填）** — maker 一次；审核人已自动选。
2. **确认批准（推荐默认）** — **checker 账号**登录后一次（会自动读提议、默认批准）。
3. **确认启用预算** — 切回 **maker** 一次。
4. **确认生成费用配置** — maker 再一次。
5. **unknown/unresolved：** 高级里 **查询费用原请求**，禁止重复 POST。

## 办理后

把 **proposalId**（可打码）告诉助手，用于只读对账；**不要**发密码或 Token。

## 对照材料

- `cost-parent-review-material.md`
- `paired-window-review-material.md`（cost 完成后才办 window）
