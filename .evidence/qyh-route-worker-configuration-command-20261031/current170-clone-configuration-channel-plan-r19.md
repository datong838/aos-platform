# a0v_170 克隆配置保存专用通道演练方案 r19

时间：2026-10-31（Asia/Shanghai）
范围：仅 `qyh-current163-to170-offline-restore-r1-20261031-pg` 克隆

## 1. 前置事实

- 克隆已从权威卷一致恢复并一次迁移到 `a0v_170`；
- 来源权威库仍为 `a0v_163`，正式配置 POST 仍为 405；
- 克隆旧业务数据、旧角色、成员关系与 grantor 均已证明保持；
- 克隆端口 18459 只发布本机回环，未连接正式 API；
- `public.bundle_installation_command` 已启用并强制 RLS；
- 专用角色和专用策略在克隆中均不存在。

## 2. 固定对象

- 登录角色：`aos_route_worker_lifecycle_command`；
- 策略：`route_worker_lifecycle_command_scope`；
- 目标表：`public.bundle_installation_command`；
- 唯一正向租户：`org-org/dev-project`；
- 身份文件：`.evidence/qyh-route-worker-configuration-preview-runtime-20261031/private/route-worker-lifecycle-command-clone-r19.json`；
- 测试幂等键：`qyh-config-channel-r19-20261031`。

## 3. 数据库准备

在一个事务内：

1. 断言角色与策略不存在、表 RLS/force RLS 已开启；
2. 创建 `LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOREPLICATION` 角色；
3. 只授 public schema USAGE；
4. 只授目标表 SELECT、INSERT；
5. 创建只面向该角色的 permissive `FOR ALL` 策略；
6. `USING` 与 `WITH CHECK` 都固定为 `org_id='org-org' AND project_id='dev-project'`；
7. 提交后用产品探针以只读事务核验全部权限合同。

克隆使用隔离环境的 trust HBA，因此角色不设置密码；正式环境仍必须使用受保护凭据，不能复制该实验连接方式。

## 4. 真正权限矩阵

产品探针通过后，分开事务验证：

1. 正向租户插入一条明确测试回执并读回；
2. 跨租户插入被 RLS 拒绝并回滚；
3. UPDATE 被表权限拒绝并回滚；
4. DELETE 被表权限拒绝并回滚；
5. 其他业务表写入被权限拒绝并回滚；
6. 再次运行产品只读探针，证明没有权限漂移。

测试回执属于隔离克隆的追加式证据，不删除、不改写，不进入来源库。

## 5. 撤销

验证完成后：

1. 移走身份文件；
2. 在克隆中撤销目标表权限与 schema USAGE；
3. 删除专用策略；
4. 删除专用登录角色；
5. 保留测试回执和无秘密证据；
6. 核对除这一条已知测试回执外，旧数据与迁移后目录摘要不变。

若任何写入结果 unknown，不执行撤销或重试，先只读查询幂等键和目录状态。该演练不开放正式 POST，不增加客户配置或业务验收数字。
