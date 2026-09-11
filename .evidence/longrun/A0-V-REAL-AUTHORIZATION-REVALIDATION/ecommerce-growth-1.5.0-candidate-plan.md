# Ecommerce growth 1.5.0 immutable candidate 方案

日期：2026-09-12

## 审计结论

现有 `solution.ecommerce.growth@1.4.0` 是 73 文件的已版本化快照，完整树 hash 为
`sha256:4dc6cfbeadc2c50d9bcdbaf85fc78b0aa9f8174db525c696e6c23dadcfaf43b3`，backend 20 文件 hash 为
`sha256:959f154b717d31c3d09451a2dde9d837993d69aa85be5c7c23afe06cee555649`。它必须保持字节不变。

当前作者 backend 已演进为 34 文件，树 hash 为
`sha256:0d9a0b6988c1ffbfb79ff4ab2389f4038d81385ab2735389a8a800901c85c302`：相对 1.4.0 新增 14 个
经营参谋/阶段评审模块，修改 `__init__.py`、`content_capability_runtime.py`、`sdk_ports.py` 三个文件。
`ecommerce_growth_review_advance` registration id 不变，但现在在 signed runtime 内严格承接五种消息：
command identity、review slot、runtime、eval proof、structure case。

当前 runnable candidate 测试把 1.4.0 backend 与持续变化的作者树比较，实测 1 failed / 4 passed。失败说明
测试的“latest mirror”假设已过期，不说明 1.4.0 被修改。

## 1.5.0 构建规则

1. 不修改、覆盖、补文件或重新签名 1.4.0。
2. 新建 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0/`；以 1.4.0 完整目录为固定 base，
   将 backend 整体替换为当前作者 backend，manifest 把 version 提升为 `1.5.0` 并更新 displayName；同时只将
   八个 workshop/analyst-template 文档的自有 `bundleRef` 从 1.4.0 提升到 1.5.0，满足 loader 的内部坐标一致性。
3. 保留 1.4.0 candidate 专属 content：七个 production profiles、media production templates、cost projection
   contracts；本波不把作者目录缺失误判为删除。
4. schema compatibility/requirements 沿用 no-package-migration 的 `a0v_001` 契约；若作者 backend 不引入新表，
   两个文件必须保持字节相等。任何 schema 需求变化必须另开 migration 波次，不在 candidate 中暗改。
5. 构建器 `RUNTIME_CASES` 的 current growth coordinate 提升到 1.5.0；1.4.0 不再参加“与作者树相等”测试，
   改为 exact 73 文件完整树与 backend tree hash 基线。
6. 1.5.0 runnable test 要求 backend exact 等于作者树、manifest/version/dependency/8 modules 正确、注册仍为
   9 个 operation、五种 stage-review 消息正向可调用，未知消息和其他 registration-only operation 拒绝。
7. Candidate 生成后只做 preflight、isolated import、合同测试和 closure；OCI build/qualification、签名、
   Registry publish、composition/Installation upgrade 分别留在后续波次，以 Receipt 串行推进。

## 预期修改目录

- `bundles/candidates/ecommerce/solution.ecommerce.growth/1.5.0/`
- `scripts/build_ecommerce_runtime_candidates.py`
- `services/aos-api/tests/extension_runtime/test_runnable_ecommerce_candidates.py`
- `services/aos-api/tests/extension_runtime/test_ecommerce_runtime_candidate_builder.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 下一波退出条件

1.4.0 tree hash 固化且工作树零差异；1.5.0 backend 与作者树 exact；candidate manifest、9 operation、五消息、
schema requirements、8 modules、builder preflight 全绿；hash、closure、独立提交完成。之后才进入隔离 OCI
build/qualification，不直接发布或安装。
