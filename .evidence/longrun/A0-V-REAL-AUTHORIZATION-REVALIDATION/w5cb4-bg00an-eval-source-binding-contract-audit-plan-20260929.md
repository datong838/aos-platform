# W5CB4 BG-00an｜Skill Eval writer 正式来源绑定合同只读审查

## 范围修正

BG-00am 将下一项写成“签名 G2 来源绑定门”。复习 228 G2.2 后需要先区分**签名增长包中的 G2 placeholder**与**AIP-4 Eval 的 Suite/Dataset/Case Artifact/Judge/Run 来源**：二者不能凭名称直接画等号。此波先读产品和现有 Store/Runner/Schema 的来源合同，审计 BG00ak writer 是否可能绕开正式 Dataset/Suite 来源；定位最小可实施点，再决定下一波编码，避免给 writer 添加臆造的 signed-bundle 规则。

## 文件级只读计划

1. 读 228 G2.2、231/231-9、AIP-4 Eval 技术方案及当前 `aip_eval_writer_authority_preflight.py`、`aip_eval_authority_store.py`、`aip_eval_pack_registry.py`、迁移表约束和现有测试。只读列出 Run→Suite/Dataset/Case/Artifact/Judge 与批准/来源确切路径。
2. 当前库只读计数相关头/版本/Run/Report 与签名 G2 placeholder；用 test-only 已签 fixture 分析 writer 当前正向能否在缺 Suite/Dataset 的情况下写 Report（不向当前库写）。
3. 落精确风险及下一波可实施的最小 SQL SELECT/权限/测试范围；无合法产品合同的 G2 bundle 绑定不编码。本波无正式授权开启或架构重写。
