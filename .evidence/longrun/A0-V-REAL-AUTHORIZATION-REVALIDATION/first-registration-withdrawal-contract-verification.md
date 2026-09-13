# 首次撤回合同局部验证


## 2026-09-13T12:00:23.025184+08:00 BG-01首次撤回合同
新增严格RegistrationWithdrawalRequest及require_pristine_withdrawal，复用登记Receipt来源核验；限定无切换/无依赖且9行仍为原始登记快照。80契约/来源/回执测试通过，48含真实PG登记回归通过。尚无撤回写入Owner/数据库原子入口/UI，不能宣称撤回功能完成。当前任务A0V-FIRST-REGISTRATION-WITHDRAWAL-20260913继续ACTIVE。下一切片冻结同组锁/当前权限/CAS、不可变撤回Receipt及无引用占位原子释放。配置恢复因预算过期与评测未决仍BLOCKED，旧请求禁止盲目重发。
