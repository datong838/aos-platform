# b77 全表事件触发器与重放前受限锁组合

无prelock实际RED：B77_NO_PRE_REPLAY_LOCK_RACE ['23505','ok']，state(1,1,1)，1failed7warnings14.92s；数据库唯一约束虽挡重复event，第二同key调用失败，不等幂等成功。两精确PID等待图到known blocker后释放，失败输出保留，不xfail/不重试。

候选去trigger WHEN，pg_trigger.tgqualNULL独立读回；runtime无UPDATE(epoch)，仅EXECUTE受限exact锁函数。request工厂在真实Store _replay前锁head，不Python UPDATE；event触发器唯一推进。两个同key请求均成功revoked=true，state(1,1,1)；相同key不同body原IdempotencyConflict、已有event新keystate(1,1,2)；原rawSQL/head missing/wronghash/canary/新事件precommit rollback1/1/1→0/0/0及ACL仍通过。unrelated随机bundle rawSQL被拒，证明没有随机前缀放行。

首轮candidate通过但evaluator在旧包装器阶段，因此原输出单独保留pre-evaluator，未作为完整证明。扩展后在全表trigger仍存在/runtime无UPDATE阶段运行原restricted evaluator race，writer改用同受限锁且event-driven=true，关闭旧Python epoch UPDATE；主流程不再重复原race。最终revoke-first和evaluate-first各1passed7warnings，节点24.40/24.30s；前者SERIALIZABLE旧快照40001/评测Receipt0/Binding2，后者真实writer精确PID等eval，提交后新key42501/Receipt0。两个顺序为同一真实组合，非旧包装器替代。

最后源码扩展后重新b76/default相邻各1passed7warnings，adjacent-summary保存节点时长。编译/diffcheck通过。测试后库49，本波无启动前新计数，不宣称逐节点新增残留全量证明。finally清理trigger/functions/policy/role并恢复临时表权限，再由disposable清理库；历史库未删。仅两测试文件，不改生产Store/migration/真库135或服务，默认路径关闭不变，无UI浏览器不适用。

自复审：锁入口只有exact head存在检查，不证明可信source/签名发行/Owner/install epoch；source/head管理员fixture，函数runtime测试EXECUTE非正式身份。full-table只指当前一次性event表的候选生命周期，非部署正式库。rev=1场景，不冒充所有修订/八来源已覆盖。当前authority1329/strong CURRENT/validateGREEN，首链pending/Goalactive。下一b78正式License可信来源初始化与发行ACL审计及最小生产文件计划，见next-plan.md，不能用局部测试放行迁移或真实Host/Provider。
