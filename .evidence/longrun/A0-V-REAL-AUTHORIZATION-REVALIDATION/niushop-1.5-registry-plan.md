# Niushop1.5 本地 Registry successor

2026-09-13，基线 b366e3ef。新增 scripts/a0v_niushop_1_5_registry_successor.py 与 services/aos-api/tests/extension_runtime/test_niushop_1_5_registry_successor.py。用户已授权本地完整开发，沿既有 Registry Owner，不涉及外部发布或安装变更。

私有 profile 复用 a0v_ecommerce_1_7_registry_successor，builder 指向固定1.5。输入 .aos-recovery-20260913 的 niushop-1.5-build-v1 和 qualification；旧根固定09-12 niushop-1.4-registry/signed-bundles-niushop-1.4，共12版本；新根09-13 niushop-1.5-registry/signed-bundles-niushop-1.5，预期13。三其他坐标 hash必须与旧版本一致，旧根不修改。源码和实际构建/资格回执逐hash重验，真实三成员2048心跳已通过。

先测试profile隔离、旧根与版本数/构建输入固定，以及复用已有历史不可替换、资格不全拒绝、幂等/CAS测试。固定提交后 preflight，再 --apply：持久签名采用已授权原本地签名体系；主库备份；create/validate/publish 只增加Niushop1.5，旧三坐标应0变更；正租户安装数和canary保持。最后 .env根只按旧路径CAS切新路径并私密备份。运行中进程并不热加载，不改其凭证文件或 current installation。

完整证据包含新旧版本hash、Registry变更计数、备份摘要、安装计数、canary0。失败或未知结果先读现有状态，不盲重发，不覆盖旧包。下一项为当前实例受控升级及商品源schema核验；正式P02审批绑定必须针对升级后的真实ref，不能复用旧P01额度。

验证：新增profile先红1项，实现后新profile与既有1.4/1.7 Registry历史保护回归合计13 passed，4.72秒，7项既有warning；旧root明确固定1.4，非字符串误替换成1.5。下一步固定提交并真实preflight，再受控apply。
