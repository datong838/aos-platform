# 全目录ACL单次聚合候选

固定候选：以coalesce(bool_or(原非法条件),false) OR count(DISTINCT (c.oid,x.attname))<>5替代同集合EXISTS OR count两次扫描。保留所有schema/属性、Owner限定、grant option、权限类型、locks精确匹配和DISTINCT。空集合仍由count拒绝；NULL bool按EXISTS不匹配处理。先只读A/B，无安装。若有收益，产品仅原catalog模块，测试原catalog测试文件，需先RED与真实ACL矩阵、空集/多权限同列/重复/撤销/额外schema/非法转授权覆盖。完整Source新试验仍为必要后续，不以A/B完成。
