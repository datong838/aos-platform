# W5CB4 BG00ce｜当前 runtime 凭据独立集群轮换与恢复验证

## 执行基线

AOS-000933、m1 `9d27d1b0`；当前 `aos-a0v-recovery-pg-data` 挂载，DB `aos_current_preview_20260927@a0v_117`，签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，approved 安装1、published4、runtime binding0、网络 Proposal0。Runtime Host/worker/Provider关闭，三身份活跃 PG 会话0，18181无监听。当前 8080 仍由 `aos_app` 登录；本波只轮换泄露的 `aos_a0v_runtime_20260912`，不宣称 API 过权已解决。此 runtime 登录对当前权威 DB 的 CONNECT=false，但对 `postgres` 管理 DB 可连接；认证探针只使用后者，不读取旧 `aos_meta_head` 数据。

## 可恢复备份与隔离演练

离仓私有状态目录 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00ce-x0s2h8_x` 为0700，备份/凭据文件均0600。当前 DB 新独立 custom dump 3,955,407 字节、SHA256 `7ae11fa31798b40a8f4c4e48e4dd674278c270e0e91d32081f0a6b9ea324a05b`，`pg_restore --list` 5600 TOC项；cluster globals 敏感备份 SHA256 `4614e45c700f8edae94f237ccd3bcceaf7e021af6accc6157315c25e19afb662`，仅保存在私有目录，不展示密码哈希。`backup-manifest.json` 记录大小/哈希，旧/新三身份文件与旧密码快照均私有保留。首次 TOC 探针未加 `docker exec -i` 退出1，补上 `-i` 后退出0；不影响备份内容。

独立 `colima-aos-a0v-test-only` PG16 容器 `aos-bg00ce-isolated-pg`，独立卷 `aos-bg00ce-isolated-pg-data`，127.0.0.1:18436；测试管理员密码从0600文件经 `POSTGRES_PASSWORD_FILE` 路径挂载，不进入参数/环境值/输出。无密码 globals 结构恢复时原 `GRANTED BY aos_app` 在独立 postgres 管理员下被拒，随后仅在隔离 cluster 重放去掉 grantor 的7项 membership，成功；完整当前 DB `pg_restore --create --exit-on-error` 退出0。克隆 a0v117 与当前六张控制表计数及全行摘要逐项相同（6/6），没有读取商城源。

独立 cluster 以现有私有密码设原 runtime 登录：旧密码正向；换新后旧密码明确认证失败、新密码正向；回滚旧密码后新密码失败、旧密码正向；再次换新后新密码正向。另将敏感 globals 备份中的**原角色 SCRAM 哈希**在独立 cluster 恢复，旧密码正向、新密码失败，再切回新密码正向，证明角色备份可恢复。首次身份探针针对恢复的当前 DB 得到 CONNECT拒绝，核 ACL 后改对 `postgres` 做仅身份认证；没有用“数据库准入失败”冒充密码失效。隔离容器演练后已停止，卷与容器保留，未删除。

## 当前零执行切换与回读

切换前旧密码在当前 cluster 正向、新密码认证失败；8080 原 PID 20654 以 SIGTERM 正常停机，8080/18181均无监听，Host进程和三身份会话0。精确 `ALTER ROLE aos_a0v_runtime_20260912 PASSWORD ...`（密码仅内存），随后旧密码明确认证失败、新密码正向；既有0600三身份文件仅 runtime entry 原子替换，Web/目录 entry 不变。API 从最新 m1 代码按同一签名 Receipt 重启为 PID 29756；`/openapi.json` 与 Web `/aip/skill-publish` 均 HTTP200，签名预检再次 GREEN。当前 DB仍a0v117，approved安装1、published4、运行绑定0、网络Proposal/Event/revision0；六控制表全行摘要与切换前隔离恢复本一致。Web/目录身份连接仍正常、三身份无活跃会话、18181无监听。

工作树跟踪文件14610个，旧/新密码字面量匹配0；旧值仍在 Git 历史但已在当前 PG cluster 认证失效。结果文件 `rotation-result.json` 私有0600，仅记录无密钥结果。源码/方案一致：本波只改变 cluster 全局 runtime 密码和离仓凭据文件，没有业务表/安装/Runtime Host写入或外部动作。剩余风险是 8080 的 `aos_app` 超级用户登录、`aos_runtime` 对 ApprovalEvent 的直写权、正式第二 checker/八配置/自然首链缺失；网络 active DB门仍禁入。下一波 BG00cf 先收紧 API 数据库登录身份的 test-only 兼容路径，再设计固定网络批准 Event 的独立签发角色和原子消费。
