# Growth 包结构 case 运行 operation 验证

日期：2026-09-11

基线：`b79eae1f`

结论：作者包纯运行入口验证通过；当前已安装的 1.4.0 未修改，successor Candidate/OCI/安装仍待后续门禁。

## 实现核对

- `ecommerce_growth_analysis_advance` 只接受恰好包含 `kind/query/stage` 且
  `kind=derive_structure_case` 的消息。
- 合法消息调用同一包内 `structure_case_from_query`；三阶段返回固定 schema，不含原始 query。
- 空 query、非字符串 query、未知 stage 由既有生成上下文合同拒绝。
- 多余租户字段、其他消息、其他已注册 operation 继续 registration-only；未知 operation 继续未注册拒绝。
- 未新增公开 operation/API，未触碰数据库、Provider、Registry、Installation、Receipt 或业务副作用。

## 验证结果

- 目标运行、结构规则、来源合同、提案合同及原包骨架联合测试：`126 passed`。
- Python 编译：通过。
- `verify_closure.py --phase ar2-7`：扫描 1764 个模块，分类 127，迁移 85；hash、未分类正反依赖、跨层 import、动态引用错误均为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现与冻结方案一致：它只把已完成的纯结构规则暴露为包内可调用 operation，没有把宿主私有
Owner 或数据库连接带入领域包。主要剩余风险是运行身份尚未闭合：当前 approved Installation
仍指向不可变的 1.4.0，不能据此宣称真实首链已经调用该入口。下一波先复核剩余 PENDING 迁移
边界，再一次性冻结 1.5.0 Candidate，避免作者树每增加一个切片就重做发布版本。
