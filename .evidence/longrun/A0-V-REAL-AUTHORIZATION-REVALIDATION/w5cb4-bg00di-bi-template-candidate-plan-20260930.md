# W5CB4 BG00di｜BI 职责模板新候选制品文件级方案

## 上位复习与事实

231/231-2 要求新 runtime 内容在新候选版本构建，不改已发布 release，签名与 exact lock/安装/运行分别验收。BG00dg 的 BI 模板严格 schema 已固定六角色、能力和 return stage；BG00dh 仅完成受检签名根代码接线。当前正式 growth 1.11.0 已签名树不可变，候选源码 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0` 的当前树 hash 为 `47b1b5ff4093ba76606b8a54867dde312d94ee3565eff959087225b4157e6b4c`；它没有 `content/responsibility-templates/`。现有签名脚本 `sign_ecommerce_current_candidates.py` 与 build profile 固定 growth 1.11.0，不能拿来声明 1.12.0 正式发布。

## 本波范围与次序

1. 在 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_1_12_candidate.py` 先 RED：新 1.12.0 候选必须为独立目录、含严格六角色 BI JSON、manifest 暴露精确目录、新版本 self refs 一致；不得携带旧签名、旧 eval、旧 runtime image index 与 lock；原 1.11.0 hash 不变。重复创建/源树漂移必须拒绝且无半成品。
2. 新增 `scripts/prepare_ecommerce_growth_1_12_candidate.py`，从固定 hash 的 1.11.0 候选复制到独立临时目录，只换 manifest 版本与 8 个 self refs，新增 `content/responsibility-templates/business-investigation.readonly.json`，由 BG00dg 的 canonical blueprint 构建并用严格模型校验；manifest 的 schemas export 纳入该目录。删去旧 build/approval 产物，写 `UNBUILT_UNSIGNED` provenance，原子 rename。
3. 执行生成器得到 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.12.0`，跑候选、schema、manifest、旧版兼容专项与语法检查；静态核对 1.11.0 hash 及当前 signed tree 未变。然后审查并落 verification。

## 明确不宣称

本波不签名、不构建 OCI、不 publish Registry、不变更当前 installation/lock、当前 DB 或已有签名树；因此只得称候选内容就绪，不得称当前正式身份/配置/首链通过。下波独立建立 1.12.0 build/sign/审批证据与合法安装迁移方案，当前库写入仍需一致备份、克隆全链演练和零执行窗口。
