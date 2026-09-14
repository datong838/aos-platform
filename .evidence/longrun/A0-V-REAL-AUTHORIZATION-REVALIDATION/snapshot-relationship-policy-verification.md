# 通用声明式关系核验验证


SC4-5g3：通用SnapshotRelationshipPolicy编译及有界assessment完成，不含Niushop业务字段硬编码。只输出两端真实未软删的candidate link，missingReference/invalidReference/missingParent/deletedEndpoint/allowedUnset分别计数，不补对象、不推断删除、不授予Readiness。严格1..12对象、1..32规则、每类<1000、每引用<=32、总候选<=24000；canonical policy hash重验防dataclass绕过。77项组合测试通过4.25秒（新30+原核心模型+既有诊断）；哈希伪造反例先1失败29通过，修复后全通过。AR2扫描1915模块五类错误为空。下一项：不可变领域包14条规则声明及实际同批核验，再接原组输入/应用Owner与质量门。

候选关系在原_normalize_rows规范化通过；观察时间统一UTC并标记不是源修改时间。旧ec_link_builder未修改。无真实源调用、主对象/关系写入、正式Fulfillment或发布。pure assessment要求后继Owner提供同组原输入并核验签名规则资产，不能单独充当权限。
