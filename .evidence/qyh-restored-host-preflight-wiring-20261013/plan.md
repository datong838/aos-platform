# 当前恢复库预检接入原 RuntimeHost 选择器

Rules：沿 231 原状态机及已批准恢复方案；aos-engineering-delivery 的方案→RED→最小改动→专项/相邻→复核→Delivery。唯一 m1 写者，不改用户已有正常代码、库卷或数据。本波修改目录：services/aos-api/aos_api/asset_registry/control_wiring.py、services/aos-api/tests/extension_runtime/test_qyh_restored_host_wiring.py，证据本目录。

候选 A：已完成的只读 restored preparation adapter 接到原 builder，依赖上一 Task 108 tests 和 PASS4/4，当前代码授权已具备；实际启动仍需独立正式身份/Owner/配置/预算门。候选 B：原独立 clone Source reader 锁兼容演练，依赖该已登记 Lease 和 lab，当前库只读。选择 A，本波只做代码接线，不设置开启环境或重启服务。

保留既有 _current_a0v_host_preflight 参数和历史 signed receipt 路径。增加两个明确 opt-in 环境字段 AOS_CURRENT_RESTORED_API_IDENTITY_FILE、AOS_CURRENT_RESTORED_INSTALLATION_ID；任一字段存在即选择恢复路径，包括空值，不允许失败回退。必须两者非空，preparation_only=True、signed_receipt 为空，现有 bundle root/trust roots/三平面 credential 均绝对路径。调用上一 Task 原脚本明确恢复 CLI；报告仍经过原 outcome/authorization/scope/mode、当前 API 数据库物理 authority 和根目录、身份文件 generation pin 核验，并额外绑定恢复安装 id 和 aos_meta_head。FULL 模式及混合输入拒绝；原 Host enabled 默认行为保持不变。

RED：精确参数派发及报告绑定，半配/空值/混合/FULL/相对路径不得启动子进程或回落；原 builder 必须在当前恢复配置下进入原 gate，Host 默认关闭仍不探测。共享既有完整后验核对，不使用假 admission predicate。专项及旧 preflight、恢复入口、UI wiring、runtime identity 相邻回归；独立冻结资料审阅。没有新 UI 改动，浏览器不适用；不会把 test 或 PASS 当八台已恢复。
