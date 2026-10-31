# 工程检查点 r1

时间：2026-10-31 23:06 +08:00

## 已完成

- 正式登记 Task `qyh-m2-guard-policy-human-approval-entry-20261031`，Authority `AOS-002055`，Lease 至 2026-11-02 20:00 +08:00；登记前目标源码无未释放 Scope 冲突。
- 先写 `plan-r1.md`，再按方案实现。
- 新增 Egress/Data/Quota 共用的隔离审批 issuer wire contract、client、process、API application。
- 新增守护策略 proposal、decision intent、decision inquiry 三个产品 API；未配置 issuer 时默认关闭。
- 新增模型运行工作台真人审批面板。批准/拒绝无默认值，首次提交后冻结，unknown 只能查询原请求。
- 复用既有 `GuardPolicyIssuer` 与 maker-checker/源草稿重核规则；没有修改底层审批、消费或激活实现。

## 验证

- 后端纯单元：`4 passed`，覆盖严格合同、非法 method、同 OIDC 绑定、先落 attempt、重复请求转 inquiry、未配置关闭。
- 前端定向与相邻回归：`19 passed`，覆盖新增合同/面板、ModelRuntime、Egress/Data/Network 原面板。
- TypeScript：`tsc --noEmit` 通过。
- Python：新增 6 个后端文件与 router `compileall` 通过。
- 路由装配：3 个新增路径存在。
- 当前标准 API fixture 因本机 `127.0.0.1:5433` 无隔离 PG 而 skip；未为此启动或写当前业务数据库。

## 一致性与风险复核

- 开发期登录旁路未修改；正式 proposal/decision 仍要求底层 OIDC，旁路身份不能形成真实批准。
- decision event 返回 `activationAuthorized=false`；没有 consume/activate 路由，没有 Provider/模型调用。
- API 不直接持有守护审批数据库权限；真实部署仍需独立 OS 身份、Unix socket、专用 `aos_guard_approval_issuer` 连接工厂。
- 当前只交付工程接线，尚未部署到 current stack，尚无本人真实批准，不能计真实业务验收。

## 下一步

1. 在独立 Task/隔离资源中补专用 Guard issuer 数据库连接配置与原生 PG/Unix socket 正负矩阵。
2. 接入 current stack 的私有配置但保持服务 OFF，先做只读 preflight。
3. 由机器身份创建精确 rev2 proposal；再由本人 OIDC 在页面审核。审批后仍另行登记消费/激活 Task。

## 技术债台账（2026-10-31）

- Quota 编辑器仍在 Capacity 工作台；本轮审批页暂以精确 proposal ID/version/hash 为输入，未做跨工作台自动带入。
- 未做提案列表、通知、批量审核和视觉统一；均为不影响当前最短路径的非功能项。
- current stack 独立 issuer 安装与运维脚本未在本 Task 实施，避免把高权限连接塞入 API 进程。
