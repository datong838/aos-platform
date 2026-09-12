# Niushop 1.4 不可变注册后继

2026-09-12，基线75b99eaa。真实逐文件比较：旧 signed-bundles-v7 中 domain1.3/growth1.7/operations-base1.2 与新 niushop-1.4-build-v1 对应构建只有正式签名文件差异，实际内容不变。旧根含11版本，后继仅追加 platform.ecommerce.niushop/1.4.0，最终12版本。

文件 scripts/a0v_ecommerce_1_7_registry_successor.py 将原固定旧/新数量、env备份名、报告标签、审计actor前缀及额外构建源保护路径提为常量，默认行为不变。新增 scripts/a0v_niushop_1_4_registry_successor.py 私有加载原实现，仅替换固定已知BUILD/receipt/qualification/STATE/OLD_ROOT/NEW_ROOT及platform1.4坐标，helper的builder为现有Niushop专用私有profile。不复制签名/Registry/CAS权限逻辑，不引入用户任意路径CLI。

验证 tests/extension_runtime/test_ecommerce_1_7_registry_successor.py 保持；新增 test_niushop_1_4_registry_successor.py 检查私有配置无污染、实际qualified输入精确核验、坏资格和源漂移拒绝、旧版本内容变动拒绝、后继根保持历史11项摘要且12项均通过原签名策略。实际签名使用原受保护本地key，结果仅本地可信包，不是外部发布。

执行门：先预检，正式写入前新目录数据库备份；原RegistryService create/validate/publish仅新增1版本，其余3个坐标精确匹配后重放，前后安装/旧目标版本/canary计数不变。env根CAS由v7到新niushop1.4根，私密原env备份不进仓库。现有API/Host不会自动加载新根，之后单独受控重启；未完成新安装前不认为恢复。

不卸载当前实例、不改P01、审批/源claim、Provider、外部发布、230L0或push。本波成功后安排真实新版本安装组合及旧实例正式卸载，原业务数据与Receipt保留。

实现预检：固定私有入口与旧1.7入口专项12 passed，含真实临时签名夹具的历史保留/重放、历史内容替换拒绝、不完整资格和源码漂移拒绝、根CAS与独立备份。13:02:28Z实际构建回执/资格/源基线预检PREFLIGHT_GREEN，输出树摘要58f773aed1a8ba2946d685af14d7b0fb91b9cd4c1bee183a50df534ab2fac062。尚未执行正式注册、签名根切换或安装。

相邻历史回归：1.6及growth1.5测试合计10 passed/1 failed，失败为test_successor_tree_preserves_v4_and_replays_exactly：旧_fixture使用已升级默认builder(1.7)创建目录，旧签名器寻找CURRENT_COORDINATES中的growth1.5，因此目录缺失。该测试、growth1.5 helper及默认builder均未改动（git diff HEAD这三文件为空）；本次1.4私有profile明确固定坐标，且其签名夹具与实际preflight已通过。记录历史夹具/独立旧脚本版本固定的待办，不修改目录名或伪造旧版本来掩盖失败，不声称全回归GREEN。该历史问题不参与本次固定1.4执行路径，后续历史工具可重放检查需补齐。
