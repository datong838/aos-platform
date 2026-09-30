# W5CB4 BG00dl｜当前 a0v118 新一致备份与独立 successor 克隆方案

## 上位与现状

依 231-2/231-3/231-4、BG00ck 已验证的全库恢复方法与 BG00dk 正式接入边界。当前 m1 `b6442a88`，权威卷仅在 `colima-aos-extension` 的 `aos-a0v-recovery-pg-data`，库 `aos_current_preview_20260927@a0v_118`，API/Web 监听、Host/worker/Provider/18181 关。当前库只读，不能把 BG00ck 的 a0v_117 备份当本次 a0v_118 基线。

## 文件级施工和退出判据

1. 先只读核 m1 HEAD、当前 PG context/卷/库/迁移/安装签名、operation/binding/配置零执行以及备份目标未存在。当前数据库只执行 `pg_dump -Fc --serializable-deferrable` 与 `pg_dumpall --globals-only --no-role-passwords`；输出放仓库外新私有0700目录、文件0600，SHA256、TOC、权限、数据库身份记录。备份失败保留现场，不覆盖或清理。
2. 新建 `colima-aos-a0v-test-only` 中独立 PG16 容器/卷/端口，随机独立管理员凭据放私有0600文件；不挂当前卷/源目录。恢复无密码 globals，必要的 clone-only grantor 规范化须留原件及差异证据；`pg_restore --create --exit-on-error` 全库恢复。任何失败只对克隆对账，不重发未知写效果。
3. 对源与克隆的 version、安装/lock/Registry/权限/运行控制表做同截止面行数与全行摘要，所有表名固定白名单且连接只读；证明旧 signed receipt/approved 安装在克隆可读。克隆不启 Host/worker/Provider，不接商城源。
4. 另写 successor dry-run 的精确文件计划与 RED：新 1.12 开发签名与当前 trust root 不同，克隆必须先走批准来源/轮换门；旧 lock 不变、新 composition/安装转换必须幂等/CAS/Receipt，错租户/签名/审批拒绝。缺合法正式 authority 时仅做隔离代码/克隆，不动当前库。

本波不迁当前库、不开自然执行，不删除旧卷/备份/库/容器。浏览器验收若无 browser-pilot 只记录不可用，不用 HTTP 200 代替。

## 克隆恢复后的 successor 文件级 RED 入口

BG00dl 将新备份、全库恢复与控制表摘要先做成可复核基线；正式 Registry/Installation 写入留到 BG00dm 独立波。先复习 `231-2/231-3`、当前 `registry_service.py`/`registry_store.py`、`composition_service.py`/`composition_store.py`、`installation_service.py`/`installation_store.py`/`installation_revalidation.py` 与 `release_policy.py`。旧 `scripts/a0v_current_preview_registry_publish.py`、`scripts/a0v_current_preview_installation.py` 固定 a0v_107 空库及 growth 1.11.0，不复用为升级入口。

BG00dm 先在 `services/aos-api/tests/asset_registry/` 精确新建 successor 克隆 PG 合同测试，再考虑新 `scripts/a0v_growth_112_successor_clone.py`（仅 test-only 连接，默认 dry-run）。RED 至少覆盖：当前旧 lock/安装和四个旧 Registry row 字节不变；新 growth 1.12 的 key/trust-root 与批准来源失配拒绝；maker/checker 非独立、错租户、错 ETag/Receipt 与重放均拒绝；成功路径只能产生新 immutable release/composition/installation 及新 Receipt，不可把旧 approved@3 原位改写；所有失败无 Host、worker、Provider 或外部效果。若正式组织批准、三身份/Owner 缺失，当前实例仍停在只读，克隆演练也不得自称正式授权。
