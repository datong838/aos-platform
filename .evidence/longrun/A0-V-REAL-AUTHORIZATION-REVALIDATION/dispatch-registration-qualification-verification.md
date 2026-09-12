# 首次登记签名包资格验证

2026-09-13，基线 c5c43801。使用现有 RuntimeReleaseRevalidator 同事务 Registry 锁、ReleasePolicy 当前信任根/发布证据检查；新增固定九项经营 API 声明资格，不凭包名放行。新检查尚未接入正式登记 Owner/HTTP，不授予执行权。

RED：新模块缺失时测试收集失败。首次真实检查拒绝：锁内 23 项 contributions 与签名清单内容相同但顺序不同。只读复核 sameOrder=false / sameSorted=true，确认不是签名漂移。修复复用 registration._index 的语义索引，新增顺序无关 fingerprint；原 backend_claims 摘要保留，RuntimeReleaseCheck 仅追加 backend_claim_fingerprints。重复 conflict key 继续拒绝。新增负例曾因错误文本由 ResolvedBundle 提前拒绝而失败，修正断言匹配现有前置校验，没有放松产品拒绝规则。

07:09 当前真实主库只读资格通过：安装 eda57424-b8cb-401e-a6f7-94220cb4f9ef@5，经营包 solution.ecommerce.growth@1.7.0，九个 POST/exclusive API 完整；证据 first-dispatch-current-release-qualification-v1.json。businessWrites=0/sourceRowsRead=0/executable=false。未执行 027 登记、未部署 026/027、未重启 API。

AR2 清册 ar2-7：1816 扫描、158 分类、93 迁移，五类错误均空。测试覆盖固定接口缺失/重复/错方法/错路径/错操作/额外 API、包标识/类别、backend 缺失、摘要不符、当前发布检查拒绝及声明重排；现有签名策略和登记比较测试一起回归。单元编排替身只证明调用和拒绝逻辑，真实签名核验以本次只读主库证据为准，不声称真实登记事务已经完成。

下一波：把资格检查强制接入登记 Owner 同事务，拒绝或结果异常时确保零路由/零回执写入；继续正式控制平面连接与 HTTP、权限评审、首次 fenced exact 切换及未激活撤销。最终目标仍是源事件自然触发首链，再八工作台真实场景与连续观察。

最终回归：58 passed（4.14s），7 项既有警告。git diff --check 通过。顺序差异修复后真实资格核验通过，未调整信任根、签名证据或候选包内容。
