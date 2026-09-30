# W5CB4 BG00df｜签名职责 artifact 类型门文件级方案

## 上位与发现

231-2 要求运行/内容 artifact 与签名声明、摘要、实际字节一致；BG00de 证 BI 首链需要精确职责模板且当前 1.11.0 没有该 artifact。源码复审又发现 `InstalledProductionProfileResolver.resolve` 对 `ResponsibilityTemplateRevision` 只查安装/签名/artifact ref/hash 行，未读 artifact 字节或校验 schema；现有测试把 `content/production-profiles/ecommerce.content-campaign.json` 标成 `ResponsibilityTemplateRevision` 还断言通过。它可能把真实签名 profile 的类型误称成职责模板。先封这条独立的类型混淆，再设计新版本 BI artifact；不在此波复制/重签整个 growth 包。

## 最小文件

1. `aip_responsibility_template_authority.py`：对 `ResponsibilityTemplateRevision` 的 installed resolver 要求从经 lock/签名/摘要验证的不可变 release mirror 读取原字节，并解析为现有 `MediaResponsibilityTemplate` 精确 schema；当前唯一已签名职责模板家族即 media。资源类型错误或生产 profile 字节、错 hash/path/安装一律 false。其他 profile/stage/evidence/eval 资源类型的 `resolve` 历史行为不在本波改变。本地 BI 兼容特例保持独立，不能作为当前签名来源。
2. `tests/aip/test_aip_responsibility_template_authority.py`：先 RED：签名 production profile 即使 ref/resourceType 伪装成职责模板也拒绝；真实已签名 media template 同 exact install/lock/hash 接受；错 schema、path、digest、未 active、跨租户拒绝。更新旧 mock 为真实 media artifact 语义，不把 mock 行当有效签名模板。
3. 新版 BI template 的候选版本、manifest、Registry artifact 与 materializer 切换在**下一波独立文件级方案**施工；需要产品 schema/gate/assignee 来源及安装升级/回滚，不修改当前 1.11.0 候选/签名树。本波只是类型门，不声称首链可用。

## 验证与边界

专项/相邻回归，源码与方案复审，当前签名/安装只读禁入复核。无当前数据库写、Host/worker 或旧 Run；未获得真实安装 active 不做正向业务验收。若旧测试暴露合理的非 media 职责模板消费，先查明上位合同再改最小校验范围。
