# 经营参谋正式 Eval case 同源绑定验证

2026-09-11，基线 `m1@2131f1b0`。

阶段评审现在从当前成功 Attempt 的 output Artifact source 重新核验 requestHash，定位唯一
query Artifact，并经私有 Owner 回读原文。case 只能由构造时显式注入的 growth 包纯函数按
stage 派生；未注入、异步返回或非对象返回均阻断。当前合同 Suite 必须绑定同一 exact
SkillTemplate，且只含一条 required positive case；其 eval_input hash 必须等于派生 case
canonical hash，eval_expected 必须存在，最终报告 caseId 必须对应同一 case。

验证结果：

- 阶段评审、包 case 派生及结构评估定向测试：修正新增负例夹具后 `82 passed`；
- D01/D02/D03 生成、receiver、worker、阶段评审与包结构规则联合回归：
  `540 passed / 21 skipped`，8.69 秒；
- disposable PostgreSQL 中真实 Eval runner、结构评估及阶段权威：`41 passed`，11.39 秒；
- 两个修改 Python 文件编译、`git diff --check` 通过；
- `verify_closure.py --phase ar2-7`：扫描 1,764 个 Python 模块，分类 127，迁移集合 85，
  hash、正向、反向、跨层导入和动态引用错误均为空。

这里的通过只证明已有报告在人工阶段决定前能追溯到同一 query/output/Attempt/Suite/Skill。
服务仍没有公开入口，且必须由可信扩展运行时把当前安装代次中的包函数注入；下一波补这一
装配及安装代次/fence 核验，再进入真实租户首链准备。
