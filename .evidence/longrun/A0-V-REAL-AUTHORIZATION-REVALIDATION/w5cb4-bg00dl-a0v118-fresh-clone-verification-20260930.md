# W5CB4 BG00dl｜a0v118 新一致备份与独立全库恢复验证

## 范围与基线

`m1@b6442a88`；当前源仅 `colima-aos-extension/aos-a0v-recovery-pg`，命名卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_118`。当前库只读；隔离目标在 `colima-aos-a0v-test-only/aos-bg00dl-isolated-pg`，新卷 `aos-bg00dl-isolated-pg-data`，回环端口 18440，PG16。所有输出状态和密码文件位于仓库外私有0700目录，文件0600；克隆管理员口令未输出。

## 命令、退出码和结果

| 检查 | 命令/对象 | 退出码与实测 |
| --- | --- | --- |
| 一致备份 | `pg_dump -U aos_app -d aos_current_preview_20260927 -Fc --serializable-deferrable`，经 `docker --context colima-aos-extension exec` | 0；`/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00dl/current.dump` 3,960,909 字节，SHA256 `796c927524d38b766813dbaa0c0201b941b72a1af7867690b8c0858a983b13e` |
| globals | `pg_dumpall -U aos_app --globals-only --no-role-passwords` | 0；`globals-no-password.sql` 3,768 字节，SHA256 `7ab08e2cfdff112b246d6b667ee4b9b4fc60431435ac9a916f5bcab20e4870a8`；未见密码标记 |
| TOC | `pg_restore --list current.dump` | 0；5621 行，SHA256 `764e610211944a6c4d4d3b8f875abec33193c416ad8d4acf39287a09eb5eca9d` |
| 克隆 globals | 克隆专用副本只去除 8 处 `GRANTED BY aos_app`，`docker --context colima-aos-a0v-test-only exec -i aos-bg00dl-isolated-pg psql -U bg00dl_admin -d postgres -v ON_ERROR_STOP=1` | 0；原件不变，克隆副本 SHA256 `cb89c01d60ca2972bea31efddde0d3d613d56bd28388c003433b902b5a8bd337` |
| 全库恢复 | `docker --context colima-aos-a0v-test-only exec -i aos-bg00dl-isolated-pg pg_restore --create --exit-on-error -U bg00dl_admin -d postgres` | 0；克隆 `alembic_version=a0v_118` |
| 源/克隆对账 | 固定 17 表 `count(*)` + `md5(string_agg(md5(row_to_json(t)::text),'' ORDER BY md5(row_to_json(t)::text)))`，各自通过只读 SQL 查询 | 全 17 表精确相等；摘要证据 `/Users/ddt/work/projects/ai_agent/.aos-bg00dl-clone-state-20260930/source-clone-digests.json`，SHA256 `4279f699cd02d1bb98c0f53f4be2d08e03c0e9a6494747de007a7e5d5eaf6953` |

17 表包括 schema version、Registry/event、安装/command/decision/event/revision、composition lock，以及 Host identity/assignment、operation/binding/configuration及修订/暂存表。源与克隆均是安装 1、lock 1、Registry 4、安装 revision 3；Host identity/assignment、operation/binding/configuration 均 0。该固定控制面摘要证明恢复一致，不能证明未来业务来源、签名批准或首链。

## 方案/实现复审和剩余风险

按 231-2/231-3、BG00dk 正式迁移方案复审：新 1.12 的本地开发签名与当前 trust root 不同；旧 approved@3/active NULL 和 growth 1.11 lock 保持原样。原 a0v_107 首装脚本要求空 Registry/安装，不适用于当前 a0v_118。BG00dm 从既有 Registry/Installation 服务的不可变版本与 CAS/Receipt 合同写 RED，再做独立克隆最小实现；当前实例缺组织批准的签发/独立 checker、正式三身份/Owner 与八配置，不能推进当前写入、Host 或自然首链。克隆没有连接商城源，没有 Run 重放、手工 run_definition、Provider 或外部发布。浏览器验收本波不适用；没有把 HTTP 页面当业务完成。
