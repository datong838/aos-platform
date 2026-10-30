# 后台处理配置命令 PostgreSQL 隔离验证结果 r2

时间：2026-10-31（Asia/Shanghai）
对应方案：`route-worker-lifecycle-command-pg-plan-r2.md`

## 结论

r1 专用连接代码已在真实 PostgreSQL 16 上通过最小权限、硬租户 RLS、越权拒绝和权限漂移拒绝验证。验证只使用一次性空容器，没有连接或修改当前业务库。

## 隔离资源

- 镜像：本机已有 `postgres:16-alpine`
- 容器：`aos-route-worker-lifecycle-pg-r2`
- 端口：仅 `127.0.0.1:55439`
- 数据：一张最小 `bundle_installation_command` 测试表
- 持久化：未挂载任何卷
- 临时身份文件：权限 `0600`，验证后已删除

容器和临时身份文件均已清理，不可恢复；它们只包含本轮一次性测试数据。

## 真实验证结果

1. 产品连接校验器接受以下真实最小权限身份：
   - `LOGIN NOINHERIT`；
   - 不属于 `aos_runtime`、`aos_app` 或其他角色；
   - schema 仅 `USAGE`；
   - 目标表仅 `SELECT, INSERT`；
   - 目标表启用并强制 RLS；
   - 命名策略只授权专用登录，USING 与 WITH CHECK 均硬编码 `org-org/dev-project`。
2. `org-org/dev-project` 回执写入和读取成功。
3. `other-org/dev-project` 写入由 PostgreSQL RLS 拒绝。
4. UPDATE 和 DELETE 均由 PostgreSQL 表权限拒绝。
5. 临时额外授予 UPDATE 后，产品连接校验器在进入业务事务正文前拒绝。
6. 撤销 UPDATE 后，最小权限连接恢复通过，原正向回执仍可读。

## SQL 表达式一致性

PostgreSQL 16 对策略 USING 与 WITH CHECK 的实际规范化表达式均为：

`((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text))`

与产品代码的精确匹配常量一致。

## 清理与正式运行边界

- 一次性容器：已删除；
- 临时身份文件：已删除；
- 当前业务库：未连接、未写入、未创建角色或策略；
- 正式配置 POST：仍保持 405；
- 正式受保护配置文件：仍不存在；
- Host、worker、Provider：继续关闭。

## 剩余硬门

真实 PostgreSQL 合同已经验证，但当前业务库仍按既定规则只读。要让运营人员真正执行“确认配置”，仍需另行准备当前库专用角色、硬租户策略和受保护身份文件，并解除该单一路由的只读 HTTP 禁入。上述动作不得借本轮测试自动执行；配置保存仍需用户明确确认，且保存后也不得自动启动业务处理。

本结果是工程闭合证据，不计为用户已配置或真实经营首链验收。
