# AR2-7D D1 配置绑定观察持久证据施工卡

基线e9043a12；AOS-000571 CURRENT/validate GREEN。沿用m1单人串行Task/Lease；复习231-6 D1 exact Owner回读要求，不前推波次。

## 文件和实现

- 新增aos_api/configured_source_observation_evidence.py及tests/test_configured_source_observation_evidence.py。复用aip_evidence，单一HostTransaction内先exact回读配置历史并匹配tenant/sourceId，再复用已有观察EvidenceStore保存v1观察，最后保存不可变组合Evidence。组合正文只包含observed Evidence exact ref、configuration exact ref、actor及明确未知语义；factIds=[]，无props/原始行/任意SQL。
- 组合exact回读完整校验aip_evidence正文/拆列/内容哈希/撤销/记录时间，并再次读取两个实际Owner：配置历史与观察Evidence；任何缺失、撤销、来源不同都fail closed。配置发生后来变化不使历史观察失真，旧ref可读，但不声明配置当前仍可用。
- 组合subject为配置exact ref、source_ref为sourceId；observed_at=读取结束，freshness_at=读取开始仅表示事件时间。created_at=clock_timestamp，晚于观察结束。新内容地址前缀隔离旧Evidence；幂等同内容重放，冲突/撤销不重发。
- 修改source_read_observation_evidence.py仅将其aip_evidence及revoke表引用明确public限定，关闭本次配置修订中已验证的同名临时表遮蔽类别；不改v1正文/hash/接口。
- 真PG测试：组合保存/两个Owner回读、回滚、并发去重、跨tenant与跨source拒绝、后来配置变化保留旧读、观察撤销使组合拒绝、组合自身撤销拒绝、拼接错误和拆列漂移；public同名临时表反例。所有运行在18434一次性库。

## 边界

这是输入配置身份与观察事件的持久绑定，不证明秘密材料版本、连接身份、上游快照或业务事实覆盖；这些未知必须保留。旧JDBC内部异常日志治理为真实连接前置门，当前仅test double。无新迁移、无Provider/真实源/发布、不push，230 L0挂起。完成后继续规范对象版本关联及DataFulfill。

## 复核时间谱系

配置recorded_at必须不晚于观察read_started_at；组合created_at必须不早于底层观察Evidence.created_at。跨时钟不满足也fail closed，不伪造时间容差。新增“事后配置拼旧观察”及组合时间倒置反例。

## 复核类型完整性补强

Python dict相等会混淆false/0及true/1；组合、v1观察及配置历史reader须同时hash原JSON正文并与重建正文hash比较，不能仅依靠dict==。因此本切片最小追加修改source_configuration_revision.py的原authority哈希核验，补布尔/整数替换反例；不改合法正文或内容地址。
