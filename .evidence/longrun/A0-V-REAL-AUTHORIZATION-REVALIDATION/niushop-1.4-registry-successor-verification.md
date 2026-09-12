# Niushop 1.4 正式本地注册

2026-09-12，c41faec5 实现。固定私有后继入口复用原签名策略、RegistryService、精确回读、数据库备份及 env CAS；原1.7默认常量值不变。当前专项12 passed；相邻历史1.5夹具失败详见方案，未以整组回归全绿表述。

13:05Z实际 --apply 完成 NIUSHOP_1_4_REGISTRY_GREEN。原11个签名版本内容全保留，追加 platform.ecommerce.niushop/1.4.0，内容摘要 sha256:05dcca8fb3f28ef338f63118a753daabe91804aec2aa4cafc76756606735bad0。只有该坐标 create/validate/publish 各1次，其余3坐标均0次。新签名根共12版本，逐版本通过原ReleasePolicy。完整结果见 niushop-1.4-registry-apply.json。

新根：/Users/ddt/work/projects/ai_agent/.aos-recovery-20260912/state/niushop-1.4-registry/signed-bundles-niushop-1.4。原 .env 根从 signed-bundles-v7 经精确CAS切换；旧env完整备份在私密state，不入库。数据库备份4,695,889字节，sha256:ec2490ad5f62e816128616fe44804c2a6731dbeed20b611f9da635edb2a5f990，独立重算相符。沿用备份helper的历史文件名不代表备份旧库，实际库固定aos_meta_head。

注册前后安装均6、正租户6、canary0，旧目标版本计数1不变。无安装、Provider、外部发布动作；本地Registry发布不是Git push，未push。API与Host进程仍旧基线/旧显式根，不能认为新版本运行已生效。

下一波：核对现有 a0fd8e25 已disabled_committed且无调度/未决调用，走正常Owner退役；固定新1.4安装state/幂等键并正常审批组合、apply/verify/configure/enable；重启Host加载新根且持续观察。P01仍禁用，主库a0v_023，受控真实源读取及八场景未完成，230L0挂起。历史1.5工具/夹具版本固定问题列入后续审计清单。
