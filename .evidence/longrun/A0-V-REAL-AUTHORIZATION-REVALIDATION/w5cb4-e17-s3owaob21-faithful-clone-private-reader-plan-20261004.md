# E17-s3o-w-ao-b21｜忠实 ACL 克隆 Reader 私有登录文件级方案

## 上位与当前事实

- 已复习 231-4、AIP-7 22、BIND-1 31、旧 `a0v_ui_read_identity.py`/`a0v_configuration_stage_identity.py` 精确 lease→clone→私有文件→当前库授权样板，以及 b17-b19。当前原卷库 `aos_current_preview_20260927@a0v_135` 仍只读，正式 Reader/Capability issuer角色0，`.env` 正式 Binding/OIDC key名0；原 DB ACL `PUBLIC=TEMP`、owner `CTc`。
- b17 忠实 ACL clone `colima-aos-a0v-test-only/aos-e17-b17-acl-pg` 仍 Up、`--network none`、卷 `aos-e17-b17-acl-data`。b18 **已经**在 clone 建 `aos_aip_binding_readiness_reader` 并精确授 `CONNECT`：clone DB ACL 另有 `aos_aip_binding_readiness_reader=c/aos_app`，独立 Reader 本地 socket 登录、全局 Capability10已通过。故不能重复宣称 Reader CONNECT 为 RED 或重复造角色。一次 `docker exec -u aos_aip_binding_readiness_reader` 因容器 OS passwd无该名字 exit1；这是 OS用户映射失败，不是 PG拒绝；不以它充数据库负门。`docker exec ... psql -U Reader` exit0。

## 本波安全最小路径

1. 先只读回读 clone `pg_hba_file_rules`、角色口令状态标志、Reader 精确 ACL/17 policy/18表读写权限、与当前原库 roles/DB ACL；不输出凭据、口令 hash 或商城源。明确本地 trust 与正式私有文件差距。
2. 仅在该 clone 以**临时 Reader专用** `pg_hba` 规则和随机口令、0700目录/0600 passfile 做本地 socket 私有文件独立登录正反链；先记录原 pg_hba 摘要与原 Reader角色配置，设计可恢复路径，确保 postgres管理员规则不被覆盖。错误文件/错租户/写权限必须失败；正确文件可读全局 Capability及 org-org scope。若 clone 现有配置不能安全定向而需扩大网络或覆盖原保护，停止这条实例实验，转文件级差距审计，不把 trust 当凭据通过。
3. 克隆内凭据证据不能升级为正式当前 API身份：签名预览 b20写门继续503；Capability issuer仍 role0、operation scoped Receipt门未齐，不授写；原库不做角色/ACL/DDL/业务写。测试结束保留可追溯证据和 clone/卷，不删旧备份。
4. 完成后写 verification、专项/相邻只读对账、m1精确提交及01/06/D-waves/Prime同步。下一依赖门另列正式 Reader/issuer凭据来源、外部 OIDC/Owner、零执行窗口与operation scoped Receipt；Host/worker/Provider关。

边界：`org-org/dev-project`唯一正向、`dev-org`零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
