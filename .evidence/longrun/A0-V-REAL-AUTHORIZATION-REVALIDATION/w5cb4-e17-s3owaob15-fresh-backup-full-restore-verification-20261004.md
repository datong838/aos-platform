# E17-s3o-w-ao-b15｜当前135新全备与独立完整恢复

## 来源与身份门

- `m1@15f5df0d` 之后无生产代码或迁移变更；原卷 `colima-aos-extension/aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`，签名 receipt 预检 exit0、Installation approved/4 published/0 runtime binding。测试 PG `colima-aos-a0v-test-only/aos-a0v-test-pg` 另卷 Up、约10.0 GiB 可用，目标库名事先不存在；API/Web 8080/8434在监听、18181不监听。原库只读、无当前库 DDL。

## 新备份与恢复实测

| 门 | 命令/结果 |
| --- | --- |
| 一致全备 | `docker --context colima-aos-extension exec aos-a0v-recovery-pg pg_dump -U aos_app -d aos_current_preview_20260927 -Fc` → 新私有目录 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob15/current-full.dump`；目录0700、文件0600，4,228,763字节；流式 SHA256 `e9038a51cee401e280d9dcfe4422f533cdb2fb407b00bd37bb21b6b5879bf498`，fsync 已执行。`pg_dump` exit0。 |
| TOC | 本机无 `pg_restore` 命令，改用 test-only PG 容器的 `pg_restore --list` 从备份 stdin 列出5905行，exit0。首次本机系统 Python3.9 调 `hashlib.file_digest` 抛 `AttributeError`/exit1；改用分块哈希 exit0，未重做/覆盖备份。 |
| 独立全库恢复 | test-only PG 原目标库不存在；`CREATE DATABASE aos_e17_s3owaob15_restore_20261004 TEMPLATE template0`、撤 PUBLIC CONNECT、`pg_restore --no-owner --no-acl --exit-on-error` 从新备份完整恢复，各 exit0。没有删除旧库/卷/备份。 |
| 双端只读同源 | 原卷和新库分别 `BEGIN READ ONLY`：均 `a0v_135`、592 public 表、12 public 序列；18 Reader 表＋8安装/Receipt控制表逐表行数与排序 JSONB 行 MD5 聚合摘要 **26/26相同、mismatch0**，命令exit0。控制表 `bundle_installation/revision/event/command/decision/registry_receipt/runtime_binding/runtime_configuration` 行数为 `1/3/3/4/1/6/0/0`。 |
| 原库后读 | `BEGIN READ ONLY` 再查 `a0v_135/Installation1/RegistryReceipt6/Reader role0/Capability issuer role0`，exit0；备份/恢复没有切换角色或写原库。 |

## 复审与下一门

- 这份新全备已证**可完整恢复且26表与当前源相等**，比仅 SHA/TOC 更强。b3 在同一135/592/12表形状已证 test-only Reader 18表 SELECT/17租户 policy 的事务 apply/异常回滚与独立登录，本波没有重复创建角色来刷新计数。
- 新库没有拟用正式 Reader/issuer 私有凭据或 OIDC/Owner，API/Web仍运行，零执行窗口未取得。当前库切换继续禁入；下波先把正式私有凭据来源、发行角色/权限/同库双身份及外部 OIDC 写入口分离成可执行门，再在本新克隆复演拟用协议。Host/worker/Provider关，八配置/六 Binding/自然首链 pending；Goal active、不 push。
