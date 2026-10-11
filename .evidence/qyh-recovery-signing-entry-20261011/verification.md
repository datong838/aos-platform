# 核验与复审

先implementation前7项缺模块RED；实施后22通过。专项真实反例：dangling receipt symlink原validate_output先resolve导致漏拒，RED1failed；解析前检查is_symlink最小修复，最终23专项/原current/Growth1.12/1.13 signer/候选相邻通过，0.76秒。

只读CLI对上一波真实build/receipt/qualification执行exit0：VALIDATED_UNSIGNED_BUILD_NO_SIGN，四版本精确core1.4.3/platform1.23.0/Growth1.13.0/operations1.2.0。独立进程确认固定signing-state路径仍不存在。tests对只读模式sign/_key调用设失败门，未创建state或签名。旧signer source/profile及版本表不改。

复审：复用原validate_qualification和validate_build实现，独立动态模块防全局污染；原hash/源码/版本/资格/Git/effects门保持。新回执output拒repo、build、state、已存在路径和dangling symlink，仅签名模式采用exclusive create防覆盖。未来本地候选Root不自动授权正式发布或当前实例运行。未实际调用sign，签名模式原原语受既有test覆盖但本新profile实际签名尚未验收；本Delivery限入口准备/只读核验。

下一项按历史恢复正式实施方案调查并实现独立HTTP入口门：精确目标库/卷/schema/租户/安装、disabled workers、有限LOGIN/OIDC/current release。正式库切换/安装配置/预算/页面与自然首链仍pending。
