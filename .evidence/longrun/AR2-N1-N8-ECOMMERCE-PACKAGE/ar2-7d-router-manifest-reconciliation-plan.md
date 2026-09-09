# AR2-7D Router 权威清单对账

基线 `m1@681ebdc7`。Rules：m1 独占串行、方案先行、最小更改、新鲜验证、逐步留证并提交；不 push，230 L0 挂起。

## 已核实问题

`bf92ff8e` 已新增 `ecommerce_growth_dispatch` HTTP Router，并直接改动生成文件 `domain_aggregates.py`；权威 `domain_manifest.json` 未登记。`scripts/generate_domain_aggregates.py --check` 因此失败，AR2 `ar2-1` 动态引用哈希也仍指向旧聚合文件。

## 修改范围

- 维护 `services/aos-api/aos_api/routers/domain_manifest.json`，以末尾连续 order 登记现有 Router，不重排既有条目。
- 由既有生成器重建 `services/aos-api/aos_api/routers/domain_aggregates.py`；预期内容与 `bf92ff8e` 的功能性改动一致。
- 维护 `dynamic-reference-phases.json` 中 `ar2-0`、`ar2-1` 的 manifest/aggregate 精确哈希，并同步 `closure-manifest.md` 的当前事实。
- 新增同名 verification，记录生成器、HTTP 邻接、闭包和哈希结果。

不改变 Router 行为、Canonical Router 语义、旧写入口或阶段权威；不借此宣称 D3/D4/7D GREEN。

## 验证

先保留已出现的生成器 RED；修改后运行生成器 `--check`、Router HTTP 专项及聚合/manifest 邻接测试、`verify_closure.py --phase ar2-1`、`git diff --check`。全程不访问真实源、Provider 或发布端点。
