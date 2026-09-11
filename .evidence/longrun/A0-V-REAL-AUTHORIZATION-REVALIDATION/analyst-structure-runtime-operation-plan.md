# Growth 包结构 case 运行 operation 方案

日期：2026-09-11

基线：`b79eae1f`

状态：实施完成，待 successor Candidate 装配

## 判断

`solution.ecommerce.growth@1.4.0` 已 canonical publish，并属于现有 approved Installation；它是
不可变历史版本，不能同步当前作者树或更换摘要。当前作者树比 1.4.0 Candidate 多出结构评估
及经营参谋切片，因此可信装配必须经后续新版本 Candidate、签名 OCI 和 successor install，
不能通过宿主 `import` 或任意 callable 冒充已安装包。

## 本波目标

复用 growth 包已经声明的 `ecommerce_growth_analysis_advance` operation，增加唯一、无副作用的
`derive_structure_case` 消息。OCI runtime 收到严格 payload 后调用包内
`structure_case_from_query`，返回无正文的结构 case。其余 analysis advance 命令继续 fail closed，
其他八个 operation 行为不变，不新增 API contribution 或公开路由。

## 合同

- payload 必须恰好包含 `kind/query/stage`，`kind=derive_structure_case`；禁止 tenant、安装、
  dispatch、权限、凭据等附带字段。
- query 必须为非空字符串且保持包内 16,000 字上限；stage 仅允许
  `portrait/diagnosis/solution-design`。
- 返回值必须完全来自包内严格派生函数，不含原 query、Evidence payload 或摘要文字。
- 未知 operation 仍报未注册；已注册但不属于该纯函数消息的调用仍以 registration-only 拒绝。
- 本波不启动容器、不修改 Candidate/release/Registry/Installation/runtime binding，不写数据库。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py` | `da1022e22035db3a84806f4730581a545cad629a998e3502d309bddf73eb7b89` | 复用 analysis_advance 的严格纯派生消息 |
| `services/aos-api/tests/extension_runtime/test_ecommerce_package_skeleton.py` | `e2bd10ddb2f846ca4b77a6f61632fa37ad71698358a2cf108051f93234bd132e` | 验证输入；文件不修改，保持九 operation 注册与既有拒绝合同 |
| `services/aos-api/tests/extension_runtime/test_analyst_structure_runtime_operation.py` | new | 三阶段正例、严格 envelope、无正文返回、其余拒绝 |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `0fac6b0433a10157870b158d482e4bd78ab3ad098e8e3475e7db16f4ef33c547` | 登记 9.8 切片 |

## 退出条件与下一门

作者包 operation、原结构规则、包边界、编译、AR2-7 closure 全绿并提交。下一门先逐项复核
第 9 节其余 PENDING 迁移边界，避免在作者树仍变化时反复冻结版本；边界闭合后创建不可变
`solution.ecommerce.growth@1.5.0` Candidate，复制当时的完整作者 runtime tree，重新生成 OCI/签名
资格，再设计 successor install。本波本身不构成当前安装可运行证明。
