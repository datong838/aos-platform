# AR2-7D D1 配置观察组合Evidence验证

- 基线e9043a12/AOS-000571；同一Task/Lease、m1串行。新增configured_source_observation_evidence.py和专项测试；复用aip_evidence，无新表/迁移。底层v1观察及配置reader有最小安全修正。
- 组合正文保存两个exact ref和actor/未知声明，factIds=[]，不保存props/原始行。写入与read_exact均回读配置历史与底层观察Evidence，校验tenant/sourceId/actor、完整正文和拆列、哈希、撤销；配置recorded_at<=观察开始，组合created_at>=底层记录。旧配置后来变化保留历史读，不重新采集。
- 新模块缺失Red后首轮3PG通过；补充51项通过。独立复核发现Python false==0会绕过dict相等，真实反例DID NOT RAISE；组合、v1观察和配置reader都增加原JSON的canonical_hash校验，合法内容地址不变。
- 修复后5文件60 passed, 7 warnings in 10.90s；最后增加早于底层时间反例后组合专项14 passed, 7 warnings in 4.26s。实际覆盖并发去重、外层回滚、跨tenant、跨source、事后配置拼旧观察拒绝、子观察及组合撤销传播、同名临时Evidence/revoke表不遮蔽public、拆列/类型/时间漂移。
- 独立只读终审无剩余阻断；组合store SHA256 69914f978218e83c8c651f0b0f9765f0c58a88c56545e6732a4de87915307a5b；v1 store 997e03f355b65b756f52d535415f30ca1a5aa44f52fe4cebf2b6f062eb9cd5d4；配置reader 9eedb19869c45e685b85f89bd9f99101637f71ec0104fd9894f181cc5dc1604f。不是外部Prime PASS。
- 闭包ar2-1扫描1699/分类85/迁移57，五类错误零，diff --check通过。只使用18434临时PG，未接真实源、Provider、外部发布或push；230 L0挂起。
- 仍只证明受信宿主提交的配置与观察输入谱系；秘密材料版本、连接身份、上游快照未知，旧JDBC内部日志为真实连接前未关闭门。下一项固定商品源行与当前规范对象的对应和字段质量；DataFulfill/D2-D4/7E仍未完成。
