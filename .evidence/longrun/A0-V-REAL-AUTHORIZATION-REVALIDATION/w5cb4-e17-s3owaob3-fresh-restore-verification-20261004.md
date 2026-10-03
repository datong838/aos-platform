# E17-s3o-w-ao-b3｜新鲜全备独立全库恢复阶段证据

按同前缀方案，源为 `colima-aos-extension/aos-a0v-recovery-pg-data` 中 `aos_current_preview_20260927@a0v_135`，目标为不同卷 `colima-aos-a0v-test-only/aos-a0v-test-pg` 的新库 `aos_e17_s3owaob3_restore_20261004`。目标库创建前只读查询不存在，测试卷约10.1 GiB可用；未删除任何旧库/卷/备份。

| 门 | 命令与结果 |
| --- | --- |
| 新一致全备 | `docker --context colima-aos-extension exec aos-a0v-recovery-pg pg_dump -U aos_app -d aos_current_preview_20260927 -Fc` 写入私有新文件并 fsync；文件 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob3/current-full.dump`，0700目录/0600文件，4,228,765字节，SHA256 `28b356f3e7c8eb3ecf7c994e205d04ee4c2ad6f575644d3d9a8044e74c6db6f1`，pg_dump exit0。测试 PG `pg_restore --list` exit0/5905行。 |
| 独立全库恢复 | test-only PG 中 `CREATE DATABASE aos_e17_s3owaob3_restore_20261004 TEMPLATE template0`、`REVOKE CONNECT ... FROM PUBLIC`、`pg_restore --no-owner --no-acl --exit-on-error` 均 exit0；失败不会覆盖旧库。 |
| 双端只读比对 | 源与新克隆均 `a0v_135`/592 public表/12 public序列；18 Reader 表＋8安装/Receipt控制表逐表 `count(*)` 与每行 JSON MD5 排序聚合摘要，26/26 相等、mismatches0，比较命令 exit0。8控制表行数依次 `1/3/3/1/4/6/0/0`。 |
| 克隆初态 | `BEGIN READ ONLY`：Reader role0、同名 policy0、Installation1、RegistryReceipt6，exit0。源继续只读、Host/worker/Provider关。 |

这是物理数据可恢复和新克隆同源的证据；`--no-acl` 并未证明 Reader ACL。下一步仅在该新克隆做事务性 test-only Reader apply/异常回滚，当前真实库不写。
