# 完整publication契约与原始签名字节阶段验收

基线4173b05e/AOS-001373；原Task gt-provider-capacity-publication-schema-20261005 lease同Owner至20:00，原登记新contracts/test范围施工。不是Task退出，不新增生产权限或迁移，未改旧issuer/原Source contracts/权威库/正常服务。

## RED/实现/回归

- 原missing-module RED 23项失败，contracts-red-r2.log；首轮自动参数ID过长日志保留原始本地路径，并lossless压缩记录contracts-red-original.log.gz及大小/hash，不伪造新RED或删除原证据。
- 新增三种严格未认证文档OriginBootstrap/SigningPermit/PublishedSource，独立purpose/目标/外部publisher/root许可范围；Source包含server UUID格式、原Source proposal rev2、独立两ApprovalEvent rev1、allocationRequest rev1、candidate/Provider/Evidence/policy/attestation/permit/origin精确refs、epoch/计量/期限/原requestHash和executionAllowed=false。UUID格式不证明数据库生成，refs/epoch只是文档字段，真实当前性与受控原出处仍由SQL承担。
- 原始bytes parser只允许三新类型与原policy/attestation，2MiB、预解析深度32、数组1000、duplicate key、float/exponent/NaN/Infinity、非法UTF8/surrogate/NUL及非规范时间/alias/空白表示拒绝；canonical bytes必须等于实际完整模型JSON dump。安全ProfileError reason不包含原文或字段值。解析不认证签名/可信key，不生成Source权限。
- 新契约初green23项，完整profile+旧Source相邻129项；独立复审发现原不完整JSON负例有间接拒绝问题后，新增完整合法原文单项变异及具体拒绝阶段，137项相邻通过。最终加入真实独立Ed25519签名+隔离PG READ ONLY组合，138项通过/7现有warnings/15.01秒/exit0，contracts-native-adjacent-final.log。
- 原生组合只用aos-ed25519-test-31dccb3dc27e及固定r4镜像：合法原文nativeverify true且解析接受；重复真实databaseOid字段原文重新签名，nativeverify仍true，解析明确DUPLICATE_KEY拒绝。说明crypto不能替代profile；合成deployment target不是生产授权。
- route_supervisor最终受邀只读复审确认专项证据缺口关闭、本波无新重大阻断；原Task保持ACTIVE。无UI改动，浏览器不适用。

## 后继必达

SQL必须独立执行同一无歧义profile，取钥只来自受控anchor/root/permit原出处，不能把本Python解析或verified布尔参数当数据库授权。完整prepare/commit同原caller、原批准/当前性/epoch协调、全域supplier+fingerprint映射、Source签发及不可变provenance/attempt一次COMMIT、consumer原生读取/拒绝仍pending。新迁移须登记152精确scope，151已占用，禁止覆盖。完整b90/八配置/自然首链/八工作台观察与发布仍未完成。
