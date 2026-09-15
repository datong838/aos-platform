# growth 1.9 内部 Registry 登记

代码基线 285b2372，先修复历史缓存污染后执行原签名继承流程。结果 GROWTH_1_9_CURRENT_REGISTRY_GREEN。私有结果 .aos-recovery-20260916/state/growth-1.9-current-package/registry/publish-result-cache-restored.json；包含数据库备份、各包状态和内容哈希。

17 个签名制品验证通过。仅 solution.ecommerce.growth 1.9.0 新建/验证/发布各一次；其余三个目标包均复用原记录、无修改。脚本 registryPublishCount=3 表示这三个阶段的 mutation 数，不能解读为三个新包发布。

before=after：installations=positive=14，canary=0；installationMutationCount=0，environmentMutationCount=0。E 未停用，F 未创建，主库尚未迁移 a0v054。源码防缓存测试 13 passed；原签名恢复 16/16。

本波 6/6 完成。下一波：核对最新数据库备份与 a0v053→054 迁移内容，验证主库角色及幂等迁移基线，然后按 F 独立配置清单执行 E 排空/禁用/脱离、创建 F、准备/验证/配置/启用。每个状态转换先读回 Receipt，结果未知不重发。仍欠真实首链、八工作台自然业务闭环及连续观察；不作发布决策，不 push，230 L0 保持挂起。
