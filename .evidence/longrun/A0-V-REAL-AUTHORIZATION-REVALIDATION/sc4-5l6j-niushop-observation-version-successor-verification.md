# SC4-5l6j Niushop P02 观测版本后继包构建与签名验证

日期：2026-09-15  
代码基线：`263435f79cd33d55ab0c728f80804348411f4391`  
对应方案：`sc4-5l6j-niushop-observation-version-successor-plan.md`  
范围：六步中的第 4/6 步；尚未执行 D→E 安装切换或真实商城读取。

## 结论

`platform.ecommerce.niushop@1.23.0` 已随 current 四包完成隔离构建、资格检查和可信签名注册。构建内容精确使用第 3/6 步冻结的候选树；core、growth 和 operations-base 版本保持不变。注册表只新增并验证 1.23 一个版本，安装记录前后均为 13，正租户安装数前后均为 13，canary 前后均为 0。

本步结论为 `NIUSHOP_1_23_CURRENT_REGISTRY_GREEN`。它只证明后继包可安装并已进入可信注册表，不代表 E 代已安装，也不代表 P02 真实批次或 ProductEvent/Case 已成功。

## 构建与资格证据

- 构建 Receipt：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/niushop-1.23-current-package/build/build-receipt.json`
  - 文件 SHA-256：`9ca68886a96940a7926e28d00a1c2265973ba5ae6bd204065e2246f3e90338f6`
  - `outcome=BUILD_GREEN`
  - `outputTreeHash=sha256:b85de41150a09527e6ee3d33d212aabe3bcd0cc192f775d0e66cab84d0ac4c07`
  - 4 个 bundle、8 个 module、3 个 runtime member、13 个 operation。
  - Niushop 1.23 源树：`sha256:51656fc4587ad3df31f14e1c057d2f09295a3c302103848ea2c3d0765e5b0a3a`，与候选生成结果一致。
  - Niushop 内容哈希：`sha256:55b29795b73d5be0f28bd68fafc48c8dd7aa42c65eb5ea130a307326e7534117`。
  - 三类副作用计数均为零：安装、Provider 调用、外部发布；注册表发布计数为零。
- 资格 Receipt：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/niushop-1.23-current-package/build/qualification-receipt.json`
  - 文件 SHA-256：`8ea1955e76315a728bb3424d3f3c4c81e65b53e616830cb7ee7b6aaae502faed`
  - `outcome=QUALIFICATION_GREEN`
  - 解析结果精确为 core 1.3、Niushop 1.23、growth 1.8、operations-base 1.2。
  - 三个 OCI 成员均完成 exact registration、alive heartbeat 和 released cleanup；临时签名未持久化。
  - tamper 拒绝覆盖 image index bytes、image digest、dependency lock、SBOM、backend、schema compatibility 和 schema requirements。

## 签名与注册表证据

- 签名前置：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/niushop-1.23-current-package/registry/preflight.json`
  - 文件 SHA-256：`6c88ca55cc2c1beeb14990b8f542e609cba3a36ccf6c1f8be67bcfe2d56214e6`
  - `outcome=PREFLIGHT_GREEN`；环境、安装、注册表 mutation 均为零。
- 签名应用：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/niushop-1.23-current-package/registry/apply.json`
  - 文件 SHA-256：`79c5450d00a58460730dc292f2b2d2a313e13cef939ff74730fe59c3e9e41fea`
  - `outcome=NIUSHOP_1_23_CURRENT_REGISTRY_GREEN`。
  - Niushop 1.23 执行 create/publish/validate 各一次；其余三个 current bundle mutation 均为零。
  - 新签名根包含 16 个历史和 current 版本；1.22 与全部既有版本内容哈希保持原值。
  - 数据库备份：`aos_meta_head-pre-growth-1.5-registry.dump`，SHA-256 `b2aae45043006be0d7e3d6f673f7dde81fe60012aa5028ad23be297066cc165c`。

## 自动化验证

定向测试覆盖候选生成、current 四包 profile 与签名 successor，结果 `13 passed`。同时通过 `git diff --check`。现有 Pydantic 字段遮蔽警告和 JDBC 退出清理日志不影响本步结果。

## 退出条件核对

1. 四包构建与资格检查完成：满足。
2. 1.23 新签名版本完成，旧签名内容不变：满足。
3. 租户安装数不变，canary 为零：满足。
4. D→E 生命周期切换：未开始，进入第 5/6 步。
5. 新鲜 P02 与 ProductEvent/Case：未开始，留给第 6/6 步及下一波真实链验证。

## 下一步

按方案进入第 5/6 步：先复核并扩展 current reinstall 控制器，记录 D exact head，优雅释放旧 Host，确认资源 released 后正式 settle D；再以 1.23 签名根创建 E 并依次 prepare、verify、stage、configure、enable，最后证明 E 为唯一 current active/ready/enabled/unfenced 且三个 OCI 与 Worker 健康。
