# 当前真实只读入口与检查点对账
Rules：用户AGENTS、aos-engineering-delivery、231八步、当前恢复方案。授权沿用父Task qyh-full-system-restoration-20261011；本项只读验证，不重启、不改当前库/生产代码、不推送。
已登记候选一：当前预算策略续期，依赖既有ACTIVE预算的合法审批路径（旧initial-budget草稿流程不适用）；候选二：当前管理入口代码/不可变来源检查点，依赖真实冻结源、专项测试及真实服务cwd。选择候选二，与费用审批无依赖。
目录：仅 .evidence/qyh-full-system-restoration-20261011/checkpoint-live-source-20261013* 与父checkpoint.json。用实际运行40434df冻结源码执行原专项测试；不使用用户工作树修改或当前库fixture，不产生权限/业务效果。校验Git原始源/原冻结manifest/current工作树精准入口文件/live API cwd一致，测试日志与输入输出SHA绑定为新aos-step-evidence。仅更新实际符合条件的current_attachment_code_and_source_verified_locally/current_immutable_source_revalidated，旧证据保留。独立review待新的精确材料审阅，不把旧review改写为当前PASS。随后继续预算续期合同调查。
