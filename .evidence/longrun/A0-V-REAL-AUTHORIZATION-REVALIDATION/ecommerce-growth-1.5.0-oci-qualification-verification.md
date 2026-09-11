# Ecommerce growth 1.5.0 OCI build / qualification 验证

日期：2026-09-12

## 结论

在 `colima-aos-extension` 隔离引擎用唯一一次 build 成功生成四包仓外输出，随后读取 exact build Receipt
完成 ephemeral signing qualification。两阶段均为 GREEN，没有重试。

## Build

- HEAD：`50a61775f01950c8b4363999f4deecc877ffa5ad`
- output tree：`sha256:ea4dab31929e45c51e5a6f023dc6eca05c0368f08a3ac102d61435ba3eec38bb`
- growth content：`sha256:416bfdb7f67ded7ab61c03efa774b5d472a3454ec681ec2aac3e8fb15a8a5318`
- growth config/image：`sha256:20feb609...` / `sha256:7850aa56...`
- 4 bundles、3 runtime members、8 modules、12 operations；BUILD_GREEN。

## Qualification

- snapshot：`sha256:3cd77511627f751a6bf3adf541ce302a9bb897471fd6fef8e68e3858325bebdb`
- resolved growth：`solution.ecommerce.growth@1.5.0`
- 3 个 runtime admission 与 3 个 `aos-platform-a0v-001` schema requirement 通过。
- tamper rejection：imageIndexBytes、imageDigest、dependencyLock、sbom、backend、schemaCompatibility、
  schemaRequirements 七项齐全。
- `ephemeralSignaturePersisted=false`；QUALIFICATION_GREEN。

两份 Receipt 的 Registry publish、Installation mutation、Provider invocation、external publication 均为 0。
临时 18436 监听与 candidate Registry 容器已清除。
AR2-7 closure 扫描 1786 个 Python 模块、156 个分类模块、93 个迁移模块，全部错误数组为空；证据 hash
与 `git diff --check` 通过。

## 边界与下一步

此结果证明 candidate 可构建、镜像身份可锁定且签名策略可验证，不等于持久 Registry release 或 Installation
升级。下一波读取 current trust-root、Registry command Receipt、actor/marking 和回滚接口，形成并执行 exact
draft→validate→publish；在发布前后分别快照 Registry 与租户 Installation，禁止把 ephemeral key 用于持久发布。
