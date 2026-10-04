# W5CB4 E17 b44：可信 evaluate 来源最小 RED 计划

## 上位约束

231 长程计划与 BIND-1 §5 要求 exact published 来源、确定性依赖快照、激活事务内重算和运行时 freshness/drift；BIND-4 复核允许 evaluate 写入版本与 Receipt。当前 E17 D-waves 的 b44 门要求证明合法外形不能冒充当期依赖计算。当前真实库 `a0v_135` 只读，正式 issuer/Reader 和 active Growth1.13 均缺，不能把 test-only 当作生产授权。

## 文件级范围

1. `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py`：复用现有完整迁移 disposable PG、非 owner test-only issuer 和 Receipt/Binding guard；新增 strict xfail 分支，只在直接伪造 `evaluate` 的位置要求拒绝，不复制数百行 fixture，也不改已有正反断言。单独正例仍显示旧 guard 接受合法外形，新增 RED 说明来源缺口。清理角色和测试函数必须始终执行。
2. `aos_api/aip_capability_binding_service.py` 与 readiness Reader：本波只读分析最终事务与连接边界；未有可信最终事务来源合同前不在服务层加一次“复查”掩盖直接 DML 缺口。
3. 当前 Alembic 头、真实卷、Host/worker/Provider 不改。唯一 `a0v_136` 需合并 b25 operation 与 b41 安装锁合同后另立迁移波，且代码/库同步切换。

## RED 与收口判据

- `AOS_DOTENV_DISABLED=1`、完整测试 PG 下，新增 strict xfail 稳定证明伪造写入能提交；原正反测试仍通过，普通 runtime 及跨租户继续拒绝。
- 回归不以 strict xfail 当生产 GREEN。若缺最终事务可信证明，交付状态保持首链 pending、生产最后 GREEN 仍 b37；下一步设计受限 DB 命令及同事务 source lock/evaluation/Binding CAS/Receipt，并在克隆先证撤销并发。
