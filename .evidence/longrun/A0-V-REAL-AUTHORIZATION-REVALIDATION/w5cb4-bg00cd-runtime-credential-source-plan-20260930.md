# W5CB4 BG00cd｜运行身份明文来源移除与安全轮换设计

## 上位方案、基线与边界

按 AGENTS.md、aos-engineering-delivery、231/231-5 的正式身份/审批与恢复边界、41 网络策略方案、BG00cb/cc 证据。当前 AOS-000932、m1 `14690b20`，权威卷 `aos-a0v-recovery-pg-data`、真实库 `a0v_117` 只读；Host/worker/Provider 关闭。`scripts/a0v_w6_bg03_candidate_scan.py` 的一处 Git 跟踪明文密码与当前 mode600 runtime 凭据相同。当前 `pg_stat_activity` 对三 Runtime Host 登录为0；8080 预览 API 使用 `aos_app`，不消费该 runtime 凭据。旧轮换程序指向 `aos_meta_head` 且已有文件时只对账，不可用于本次当前卷轮换。

## 文件级计划

1. 只改 `scripts/a0v_w6_bg03_candidate_scan.py` 的硬编码 DSN：调用既有 `a0v_ecommerce_runtime_host._load_credentials`，从固定 mode600 文件惰性读取 runtime DSN；解析后严格要求原固定 login、host、port、旧库名，失败关闭。脚本原有候选规则、租户和输出格式不变，本波不执行它，不读取 `aos_meta_head` 商品源。
2. 先在 `tests` 加无需数据库/真实密钥的负例：缺文件、权限错误、错误角色/目标与合法假 mode600 三身份文件；RED 后最小改动，再专项测试、编译、静态跟踪文件扫描，确认明文不再留在当前 Git 工作树。测试仅用假密码。
3. 本波只读盘点轮换消费者：当前 PG 活跃会话、Current API 启动身份、Host 关闭状态与受限三身份文件。记录旧轮换脚本不适用原因。当前真库不写、不换凭据、不启动 Host。
4. 轮换作为独立 BG00ce：先备份当前数据库和 PG cluster globals（角色密码是集群全局状态，单库 dump 不覆盖），验证哈希/TOC；独立 PG 集群恢复与角色密码轮换、旧凭据失效、新凭据三平面连接及回滚演练；核无活跃消费者与零执行窗口，再受控切当前角色密码和 mode600 文件、服务读回。旧 Git 历史引用需单独评估清理/访问控制，不重写 m1 历史。然后 BG00cf 回网络 Event 受控签发。

## 验证/风险

无业务数据读或外部动作；测试不以 mock 证明正式授权。源码去明文不能撤销已泄露凭据，BG00ce 前该风险仍 OPEN。轮换会影响同集群多个 DB 和潜在离线使用者，故不可直接运行历史 `a0v_bm_runtime_credential_rotation.py apply`。保持 a0v116 active 门和 E16 Host 禁入。精确 add/commit，不触碰无关 dirty 文件、不 push。
