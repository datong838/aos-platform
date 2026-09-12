# 未绑定准备资源恢复验证

2026-09-12，基线1770fae8。实际安装原始证据已归档：schema三包回执均recorded=false；新组合approved→applied@4，canary0。5分钟准备期限到达后Host v14退出，操作needs_attention/RESOURCE_CLEANUP_UNCERTAIN，无binding，核验事务被拒。

测试：首次新fixture尝试更新合成事件被不可变触发器拒绝（8失败/15通过）；已改为生成时写入完整证明，不绕过触发器。随后有效RED为1失败/22通过，精确复现无binding被拒。实现后cleanup/recovery/reset三文件58通过、1跳过；新增批量入口用例后cleanup/worker两文件30通过。跳过项不作完成证据。

实现仅在无binding且当前installation applied、无active指针、revision/lock与唯一原准备证明一致、无已提交verify、全资源精确确认released时收口。保留apply原始提交语义，追加unbound_preparation_released并清除已解决清理故障，不恢复任何资源或启用binding。已有绑定路径继续failed/PREPARED_RUNTIME_RELEASED。幂等回读强校验终结事件，事务回滚、跨租户、运行身份、原资源hash门仍保留。

计划一致性：只补清理后可正常reset的缺口；reset仍由原Owner独立复核权限/锁/资源。尚未实测新Host恢复和reset，尚未配置/启用，源读取和八工作台真实闭环未完成。API仍旧进程，后续必须明确重载。

实际恢复：e904c438后Host v15于14:10:08Z启动，PID98435，唯一运行；14:10:32Z正常宿主恢复批次已将原操作清理故障收口，applied@4保持，无binding、canary0。观察文件niushop-1.4-after-unbound-cleanup.json。新增reset_target固定该UUID、If-Match 4与唯一reset-r4键，拒绝旧profile/旧UUID；RED1失败/3通过，实现后与原reset守卫18通过。仅调用既有LifecycleService.reset_preparation并同键回放，未手工修改主库。


## 2026-09-12 22:14 未绑定准备期限恢复

e904c438修复applied且无binding的清理收口，1652c510增加精确reset入口；Host v15 PID98435已恢复并收口原操作。14:13:22Z正式reset使afd792de-e85e-4680-86d0-c83404824fb3从applied@4回到approved@5，同键第二次replayed=true，canary0。资源仍released、未配置/启用、无源读取。cleanup/recovery/reset58通过1跳过，追加batch/worker30通过，reset入口18通过。主API仍旧进程，主库a0v_023。下一波：先补新profile配置/多次apply后的精确代际观察入口，再正常apply→及时verify→四来源配置/启用→跨期限连续观察；随后受控源claim/读取接线与主库迁移。不得把apply的succeeded当作资源可用，查看released记录与清理证据。
