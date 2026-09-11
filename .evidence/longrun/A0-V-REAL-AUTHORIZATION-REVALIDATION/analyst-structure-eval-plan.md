# 包内固定结构评估

2026-09-11，基线b8bae617，延续231-1/231-5/分析160与前波方案。m1单人串行，不push、不主库、不新增API。

文件：bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_structure_eval.py；services/aos-api/tests/extension_runtime/test_analyst_structure_eval.py；闭包及验证证据。

接受唯一aos.eval-text-subject-input/v1信封。实际正文UTF8 SHA必须与subjectArtifactRef一致；caseInput是版本化结构规则，带stage、唯一exact sourceRefs、portrait专用metricSources（每个指标映射一个或多个来源索引）。这些来源必须由后继宿主从当前原始输入生成并绑定到Eval Suite，包不能把调用者声明当真实数据权威。本波只实现结构函数，不将其接成生产自动通过门。

错误配置/信封/正文hash不匹配抛固定错误；合法规则下回答格式/索引失败返回结构不通过固定码；画像选用指标必须有选中的来源支持。D02/D03复用严格解析，模型不能填写权限和批准。输出只有schemaVersion/stage/structurePassed/detailCode，不输出正文、业务文本或异常输入。通过明确只代表结构及给定来源库存中的引用成立，不证明来源真实、因果、语义或经营效果，不代替人工评审。

测试先红后绿：3阶段成功、畸形回答、原文漂移、重复/类型错误来源、错误协议、映射缺失/越界、选中指标未引用支持源、深层错误固定码、不泄漏正文；独立包导入继续验证。退出条件是此纯函数与相关回归通过；下一波绑定真实Owner输入与Eval target/judge完整运行，随后阶段人工评审和恢复。

补充：metricSources是指标所需的全部支持来源集合，回答须同时选择全部来源；不能仅碰到其中一个来源就通过。
