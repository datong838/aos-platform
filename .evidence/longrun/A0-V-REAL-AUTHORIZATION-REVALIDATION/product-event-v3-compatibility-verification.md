### SC4-5i5 v3自然事件入口兼容验证

ProductEventCandidateReader和ProductEventPolicyGuard补充明确SnapshotMappingV3类型；来源仍由原SourceSelectionOwner当前编译/授权，原selection scope、shop、parent、事件证据、时间窗和同步回调检查不变。无新查询、事件时间修正、Case创建或安装。

Red5 failed/15 passed（5.26秒）证明当前v3被旧类型白名单拒绝；修复后连原callback测试31 passed（9.00秒）。覆盖v3正常、错shop、错parent与执行前/中到期。上述是明确Owner fake的接线测试，不是主系统端到端验收。AR2扫描1927/187/93五类错误为空；已有客户与数据库未变。

后继SC4-5i6：根据原事件Origin的runId查找唯一原组manifest成员，验证same cutoff而不是仅按时间拼组；定位返回只是路由，仍须原组当前Owner和原Store/投影证据验证。当前组控制为运行中守卫，未来完成态回读必须专门实现生命周期合同；不得为让分析继续而把已完成schedule假装running。正式12事实/人群计量与Outbox消费继续待做。主安装仍旧版本，不能将兼容代码等同线上恢复完成。
