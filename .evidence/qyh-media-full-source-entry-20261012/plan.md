# 栖月汇媒体完整来源入口最小修复
基线6a2ae53c/AOS-001905，复习231-9四层、原media-source-wiring-review和next-source-contract，不重建四门工作台。
候选一真实登录/独立publisher配置接线已授权但路径待答；候选二原Store完整Source入口修复已登记且可独立，不依赖真实登录，选择二。

## 具体文件/行为
services/aos-api/aos_api/aip_production_contract_store.py：新增media_gate_source_resolver(conn,scope,完整RegisterMediaGateProfileRequest)，只接受True；原Stage callback仍只用于Stage。媒体缺专用resolver时连接前拒绝；有resolver时在原contract事务中校验三refs和四gates输入，批准前不查重/读Rule/写Receipt或业务记录。未分类故障不吞并，原事务负责回滚。
services/aos-api/tests/aip/test_media_full_source_entry.py：RED证明旧Stage True不能授权媒体，全文/同事务传递、非精确True拒绝、拒绝前无SQL/无commit、resolver错误回滚、无降级。
services/aos-api/tests/aip/test_w7_06_media_four_gate.py：既有隔离集成fixture保持明确test-only Source double，新增专用参数，不能当真实签名校验。

## 真实退出/边界
入口修复不等于完整Source或业务恢复。router不配置恒True、不借开发身份；原RegistrySnapshotReader/ReleasePolicy、当前安装与签名policy贡献/四Rule受控Producer仍是下一正式接线。默认None继续拒绝，当前恢复库Profile/Rules0，不能虚构正向原生Source验收。
先新测试RED，专项GREEN、原W7四门/Stage/BI适用隔离累计；真实当前库/商城/Provider操作0。保护旧Stage功能、原数据、签名和22个用户修改。精确提交、Delivery组件结论、CAS及7强投影同步；完整Goal active。
