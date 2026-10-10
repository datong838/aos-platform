# 完整原生末门的program-header映射身份检查
Rules：231、原联合3/11.3、原NativeEnding Task Lease，真库只读，m1单写。上一波实际同路径inode替换反例已收口；本波是原完整协议所需检查，不作为更窄替代完成标准。
候选：program-header真实映射身份与打开文件绑定（选择，隔离实现已授权）；原Main全8节点末门Source/clock/COMMIT（依赖模块/回调闭合）。
精确文件：services/aos-api/postgres-extensions/aos_admission_end/aos_admission_end.c、aos_admission_end--0.1.sql、services/aos-api/tests/aip/test_shared_parent_native_ending_pg.py；本目录证据。原pending/path/disk函数正文不改。
新增Owner-only零参loaded_module_mapping_facts()。用公开dl_iterate_phdr快照中的真实program-header地址定位/proc/self/maps唯一区间，不按路径搜任意匹配行；将其kernel device major/minor/inode与loader路径打开descriptor的fstat及随后named stat绑定。未知、重复、非文件映射、替换/deleted mismatch均拒绝；vDSO经auxv仅virtual标记。快照前后地址/header/name完全一致；固定最大8192 map行/每行4352bytes，资源ERROR清理及CHECK_FOR_INTERRUPTS。
返回schemaVersion/programHeaderMappingIdentity=true/imageBytesVerified=false/executionAllowed=false和每模块path/virtual/headerAddress/mappingStart/mappingEnd/fileOffset/deviceMajor/deviceMinor/inode。这是即时header映射身份，仅此性质，不声称所有segment完整性、映射页/构建来源、可信Root包不可变生命周期或callback最终执行。
RED Owner/ACL/API absent；正常真实kernel maps对账；唯一副本loaded后rename替换必须拒绝、savepoint恢复后原mapped inode恢复可再次读。原件均精确SHA保留。SQL尾仅原隔离fixture事务安装rollback；新artifact独立唯一/tmp，不覆盖旧库/库卷/binary。
专项+原module7项相邻0skip、Werror构建、独立rollback/schema/metadata/hash回读。未改页面Browser不适用；复审/verification/精确提交/CAS/上下文；full Task不出Delivery。剩余all-segment字节与可信生命周期/全8节点/Source/RI/finalclock/实际COMMIT仍完整待验收。
