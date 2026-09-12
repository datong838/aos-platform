# a0v_025 计划批准关联表本机部署方案

2026-09-13；c2957b89；独立m1 Lease A0V-SCHEDULE-BINDING-LOCAL-MIGRATION-20260913。范围只限aos_meta_head从024到025，及新建aos_schedule_binding_20260913_ti4_test克隆。沿用已验证的024固定目标部署方法；主Docker仍colima-aos-extension/aos-a0v-recovery-pg；不启动业务、写批准或读真实源。

新增scripts/a0v_schedule_control_binding_deploy.py及tests/test_a0v_schedule_control_binding_deploy.py，旧024脚本不改。备份目录为.aos-recovery-20260913/state/schedule-control-binding-deployment。备份0600/目录0700，已有备份/克隆/证明拒绝覆盖。prepare先主库024关键12表指纹，pg_dump完整保留ACL/owner，独立库恢复验证同指纹再正常Alembic升级025；仅一个新增表，强制RLS、不可变触发器、runtime SELECT/INSERT，3个已验证外键指向计划、exact Control和自身前序；表应空。

apply需Lease有效、m1、迁移与备份hash相等、克隆025验证通过、主库024及备份时指纹不变。数据库advisory互斥锁下只升级024→025，限制锁等待和语句超时；结束复核版本、权限/外键/触发器、12表指纹不变。失败保留备份/克隆/证据，不stamp、不破坏性降级、不清库。API维持旧进程，后续权限与入口审计通过再重载。
