# Niushop 1.4.0 声明式P01快照候选

2026-09-12，基线e8ada19e。已登记A0V-NIUSHOP-1-4-SNAPSHOT-CANDIDATE-20260912 m1 Lease。新增scripts/prepare_niushop_snapshot_candidate.py、scripts/build_niushop_snapshot_candidates.py及bundles/candidates/ecommerce/platform.ecommerce.niushop/1.4.0；对应tests/extension_runtime/test_niushop_snapshot_candidate.py。不改已发布或当前安装目录。

源1.3.0树摘要固定sha256:f79374cef9fbd6c5a55e312b1e18f4bdaeabecb756d95128d82fc8eda28c73bd。准备前要求旧树精确匹配、目标不存在；复制忽略pycache，只有bundle.yaml版本1.4.0与P01 mapping新增snapshot_materialization两处变化。声明schema_version=aos.snapshot-materialization/v1、platform=niushop、shop_key=site_id、source_timezone=+08:00、property_defaults=status active/currency CNY/timezone +08:00。缺省含义沿上一波方案，不代表从源表读得营业状态。

现有候选源树不包含生成的runtime-image-index，因此本波不能把源复制视为完整可安装包。新build wrapper在独立加载的原builder模块实例内选择平台1.4.0，其余domain1.3.0/growth1.7.0/operations-base1.2.0保持现有配置；复用原preflight/build/qualify全部检查，不改原builder默认全局状态、不复制整套构建实现。暂不注册发布/切安装/启用管道。

验证准备函数拒绝旧树漂移/已有目标、旧树不变且只两文件不同、新声明可编译且源PII排除不变、wrapper静态预检4包3运行成员8模块12操作。需显式--build才进入隔离Docker引擎，输出目录必须在仓库外且全新；真实镜像构建/资格测试单独落证据，不使用假成功或改验收条件。

下一波在隔离环境构建和验证新组合，再走正式发布/新版本安装配置及审批；原运行保留直到新实例证明可替代。真实P01源调用仍需独立占用提交/有界读取与原批次准备接线，不开启旧live捷径。

证据复核补充：新候选不能直接继承旧bundle-evals的passed标签。prepare先将新副本的评估状态置pending，再实际执行映射编译、合成对象接纳、PII拒绝等静态评估，成功后写带明确范围与映射摘要的新bundle-evals。因此最终差异为manifest、P01 mapping和该评估证据三文件；并非仅两文件。静态评估passed不替代OCI资格/当前安装/真实业务验收。prepare中途失败保留新副本pending供调查，不覆盖旧目录或自动重试。
