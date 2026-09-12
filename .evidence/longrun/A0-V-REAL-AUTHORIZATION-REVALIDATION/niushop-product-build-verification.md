# Niushop 1.5 构建与隔离资格验证

2026-09-13 03:14，源提交 e957488c，候选源 e6761c1d。独立 profile 测试先红1项；实现及原 builder 联合12 passed，4.56秒。随后实际 BUILD_GREEN / QUALIFICATION_GREEN。

构建输出树 sha256:d4d67c2095442ee6b3f48da4559448017beefa3b8c43e138caa0091ff7fc11fd；独立回读 outputTreeHash、contentHashes、qualification buildReceiptHash 全部相符。四坐标 core1.3、Niushop1.5、growth1.7、operations-base1.2，三运行成员、8声明模块。声明模块数不代表真实八工作台已可用。

实际 OCI 三成员分别完成 exact 注册、2048 heartbeat、released，贡献数1/2/23；七类篡改拒绝 imageIndexBytes/imageDigest/dependencyLock/sbom/backend/schemaCompatibility/schemaRequirements。临时签名未持久化；Registry publish/installation mutation/Provider/external publication 均0。原始 build 与 qualification JSON 已归档。

03:12:42 当前安装实例 afd792de-e85e-4680-86d0-c83404824fb3 继续运行，282次续租、17473.5秒，隔离canary安装0；详见 niushop-1.5-build-host-continuity.json。此为基础运行观察，不是经营效果观察。

本波未安装Niushop1.5，API也未加载商品v2转换；实际Product源schema、真实P02、自然Case/Run、生产前端入口仍待处理。下一波先复核Registry successor仅追加新版本的条件和当前安装方案，再进行受控升级与商品源接入，不重跑P01已耗尽审批。
