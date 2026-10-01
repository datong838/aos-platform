# BG00GW-a2 verification

基线 AOS-001065 / m1 4b1d5dec。原注册 operation 下新增固定结构评测消息，复用原 query 推导与原结构评测算法，无 IO、权限、schema 或当前安装变更。

## 实测

- RED：新测试通过原 package.handle 调用，14 failed / 1 passed，exit1；原 dispatch 在 registration-only 边界拒绝缺失消息。
- 首轮累计：116 passed / 7 warnings / 4.72s，exit0，零跳过。
- 接续现场重新累计：116 passed / 7 warnings / 4.93s，exit0，零跳过。
- 命令（services/aos-api）：`.venv/bin/python -m pytest tests/extension_runtime/test_analyst_structure_eval_operation.py tests/extension_runtime/test_analyst_structure_eval.py tests/extension_runtime/test_analyst_structure_case.py tests/extension_runtime/test_analyst_stage_review_runtime_operation.py tests/extension_runtime/test_ecommerce_analysis_start_operation.py tests/extension_runtime/test_analyst_package_proposals.py -q --tb=short`。
- 三文件 py_compile 与 git diff --check 均 exit0。

## 复审与限制

15项新测试覆盖三阶段正向、真实结构负向、正文/来源hash漂移、参数精确性、错误operation/kind、输入不变及错误不回显文本。来源为显式测试fixture，不是当前正式generation或业务验收。
接口严格五键，结果不含 gatePassed/执行许可/正式Report；没有重写算法。源代码接线尚未重建签名制品、OCI安装或运行Host；浏览器不适用。原 InstalledGrowthStageReviewPort 仅校验五类 review 消息，不能把新的 analysis 评测消息直接加入它冒充签名生产链。
下一波应补完整签名输入及正式阶段Eval producer设计，再衔接 accepted阶段决策到Handoff；自然首链、每日新版本恢复及八工作台真实验收仍未完成。

## 日志 SHA256
- `/tmp/aos-gwa2-red.log`: `8af579f0230312c55fc6916fde70c38c737f579d2635017bf60027ecccf13668`
- `/tmp/aos-gwa2-regression.log`: `9a030734464f2b6126d9e30ccaae224ea1057bbb038aa9bd0e8952ea4b7fff84`
- `/tmp/aos-gwa2-regression-current.log`: `3fd07d2eb1b44e4ff8eb02e02a5db26213b261a855a42e7202636044c3d5df3a`
