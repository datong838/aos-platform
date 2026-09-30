# W5CB4 BG00di｜BI 职责模板 1.12.0 候选验证

## RED 与实现

复习 231/231-2、BG00dg/dh、既有 1.11.0 候选与 current build/sign profile 后写文件级方案。RED：`test_ecommerce_growth_1_12_candidate.py` exit 1，3 failed，因新生成器尚不存在。

新增 `prepare_ecommerce_growth_1_12_candidate.py`：固定 1.11.0 基树 hash，原子复制到独立 1.12.0 候选；仅改 manifest 版本和 schemas export、8 个工作台 self refs，新增由严格 BI 六角色 blueprint 校验生成的 `business-investigation.readonly.json`。移除旧 bundle-evals、SBOM、runtime image index、依赖 lock 和签名（存在时），写 `UNBUILT_UNSIGNED` provenance。当前 build/sign 脚本仍固定 1.11.0，不用于给新候选冒充签名。

## 验证输出

- 生成器 exit 0，候选 tree hash `99ab0c0abbfb8c6456941402690c4134700fe34ea43a46b6d6aa6a3ebb1993dc`；原 1.11.0 hash 仍为 `47b1b5ff4093ba76606b8a54867dde312d94ee3565eff959087225b4157e6b4c`。
- 新旧树逐文件对账：新增仅 BI 模板 1 文件；删除旧 bundle-evals 与 SBOM 2 文件；变化仅 manifest、8 个 self refs 与 provenance。未触碰 backend、其他候选、当前已签名树。
- `test_ecommerce_growth_1_12_candidate.py`、1.11.0 兼容、installed resolver 与 current builder profile：exit 0，34 passed，7 warnings。`py_compile` 与 `git diff --check` exit 0。
- 模板六 slot 无 assignee；provenance 的 SHA256 对应原字节。ManifestLoader 可装载候选，重复生成和源 hash 漂移拒绝且不留下半成品。

## 结论、风险、下一波

只完成 **UNBUILT_UNSIGNED 候选内容**。尚无新版本 OCI/dependency/SBOM/eval/签名/Registry/安装 lock/当前业务授权；首链依然 pending。当前 DB、既有签名树、Host/worker/Provider 未改，无 browser-pilot 截图。

BG00dj 建立新版本的独立 build/签名可复核路径和负例；不得改动当前 1.11.0 签名树，发布/安装与当前 DB 迁移须按正式安全门另波处理。
