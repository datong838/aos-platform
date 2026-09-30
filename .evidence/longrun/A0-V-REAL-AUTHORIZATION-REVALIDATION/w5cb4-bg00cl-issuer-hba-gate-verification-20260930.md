# W5CB4 BG00cl｜网络签发者 HBA 失败封闭验证

## 范围与证据

接 AOS-000941，m1 基线 `a422872c`、数据库/代码 `a0v_118`。复习 231-4/231-5、BG00ci/BG00cj/BG00ck 后，发现当前权威库和独立 BG00ck 克隆的 `pg_hba_file_rules` 都有 `local`、127.0.0.1、::1 的通用 `trust`；只读查询退出0。当前库 issuer 仍 `NOLOGIN`，没有当前卷 DDL/DML。

先新增 `test_a0v_network_issuer_hba_gate_pg.py`，初次 RED 因缺模块在收集阶段退出2。按文件级方案新增 `scripts/a0v_network_issuer_hba_gate.py`，读取 `pg_hba_file_rules` JSON，按 HBA 行序检查 Unix socket、IPv4/IPv6 的 SSL/非 SSL 首个匹配规则；仅精确数据库＋issuer 用户的 SCRAM 规则通过，错误、未知或宽泛匹配均失败封闭。修复 IPv6 全掩码与地址族处理后的专项2 passed；与 BG00cj DB 门邻接回归8 passed/7 warnings，退出0。`py_compile` 与精确 `git diff --check` 退出0。

当前真实库只读导出 HBA JSON 输入预检命令，输出 `ISSUER_HBA_UNSAFE`，退出2，符合禁入预期；独立克隆实际 HBA 负例通过。合成的精确 SCRAM 首匹配单测只验证解析算法，不是正式 TCP/SCRAM 登录或业务批准证明。API/Web 继续当前 E16 失败封闭，Host/worker/Provider 不启，18181 不监听。

## 复审与未完成

本切片只建立可重复的 HBA 预检，不改现有 `decide_network_activation()`，不启 issuer 登录或进程。当前通用 `trust` 规则必须由独立安全切换波消除或由更早的精确 issuer SCRAM 规则覆盖，再做实际错误密码、真实 TCP 登录及非 owner 事务正反链。外部 IdP/第二真实 checker 和当前 API 受限身份仍缺，当前 approved 安装 binding0，自然首链未证明。下一波 BG00cm 继续克隆 SCRAM/HBA 正向与专用 issuer 进程接线；正式实例授权不足时只推进隔离研发。无商城源读取、dev-org 写、旧 Run 回放、手工 run_definition、push。
