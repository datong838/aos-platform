# W5CB4 BG00dn｜新 1.12 当前正式来源与配置禁入审计方案

## 上位方案与现场

复习 231-2 组织批准签名及 Registry 精确 release、231-3 安装/运行三身份与 Owner、BG00dk 当前正式缺口、BG00dm 独立克隆正向。当前 m1 `0039653e`，权威库 `aos_current_preview_20260927@a0v_118` 只读，growth 1.11 旧安装 approved@3/active NULL。克隆新增 1.12 `published` 与独立 approved 安装，但测试私有双根和 maker/checker 字符串不构成当前组织批准。当前正租户 `meta_membership` 只读汇总为 `owner|1`，无独立 checker；Host identity/assignment/operation/binding/config 仍0。

## 文件级施工

1. `services/aos-api/tests/extension_runtime/test_growth_112_formal_source_audit.py` 先 RED：将本地开发签名、缺当前精确信任、新版本未在当前 Registry/安装、独立 checker 缺失、三身份/assignment/八配置缺失分别返回禁入；任何一个缺口不得得出正式可执行。测试不造正式账号或凭据。
2. 新增 `scripts/a0v_growth_112_formal_source_audit.py` 默认且唯一只读入口：用受检旧/新签名 Receipt、当前 PG 与独立克隆的物理目标、固定控制表/成员聚合及 `runtime_configuration_candidates.read_candidates` 产生机读差异；只输出计数/哈希/原因码，不输出 subject、凭据或业务源；无任何 apply 开关。读当前实例需固定 `colima-aos-extension` 命名卷与 a0v_118，读克隆需固定 test-only 卷；连接均只读。
3. 专项/相邻回归和实际两库只读验收，方案/代码复审、verification、D-waves/01/06/Prime、m1精确提交。若当前无正式签发者/独立 checker/三身份，阻断该实例，下一波转做 1.12 signed responsibility template 到产品职责配置来源的独立 test-only 消费合同，不手造正式身份。

当前库不写、不迁移，不启 Host/worker/Provider，不读商城源、不重放旧12 Run、不手工 run_definition、不碰230 L0、不 push。
