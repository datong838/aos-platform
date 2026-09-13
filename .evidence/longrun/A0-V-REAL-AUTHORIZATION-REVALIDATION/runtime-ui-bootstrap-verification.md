# UQ5-B1 签名页面启动合同验证

日期：2026-09-13。基线：bac0a89a；m1单写者，不push。

问题：ExtensionHost只传nonce，而原ExtensionBridge的hello必须同时提供安装ID、generation、executionEpoch。签名子页面无法从父组件读取这些props，已有资源URL不等于可完成握手。

实现：ExtensionHost把公开身份、initialRoute与nonce放入URL fragment，覆盖旧fragment；查询中的签名摘要保持不变，无token/subject/roles/业务内容。身份或路由变化沿原安全指纹重建iframe、nonce及桥接，权限仍由原桥接和服务端检查。

验证：ExtensionHost、extensionBridge、RuntimeWorkshopHost共17 passed；全量Web TypeScript检查通过。新增用实际URL fragment重建合法hello、确认HTTP query未带身份、更新generation/epoch废弃旧iframe及nonce、路由变化同步初始路由。旧测试环境act警告仍存在，无断言失败。

范围与限制：本波仅代码验证；未部署主库迁移、未升级原RuntimeHost、未修改旧签名包，未声称实际新页面读取或业务闭环完成。签名资源HTTP服务与growth后继包仍待完成。

下一波：UQ5-B2按当前Registry发布证据、可信签名和精确摘要提供声明的只读HTML，随后B3后继包实际资格验证。
