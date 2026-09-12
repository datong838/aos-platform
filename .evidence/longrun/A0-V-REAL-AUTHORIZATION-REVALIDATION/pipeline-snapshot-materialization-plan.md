# 已批准映射驱动的快照对象生成

2026-09-12，基线f5e5d462。复查frozen/02通用/P01、frozen/01源字段与当前1.3.0 mapping。现有ec_normalizer.to_shop忽略field_mappings，仅固定生成name/status/currency/timezone；不能用于证明安装包控制了真实映射。因此先补纯声明解释器，再准备新不可变包版本，不改现有published 1.3.0字节。

新增services/aos-api/aos_api/pipeline_snapshot_materialization.py与tests/test_pipeline_snapshot_materialization.py。compile_snapshot_mapping(mapping,read_spec)在调用方验证当前资产摘要后，严格编译字段source/target/type（本版string/int/timestamp）、validation.required、unique_key_pattern和新增snapshot_materialization配置。后者含schema_version=aos.snapshot-materialization/v1、platform、shop_key、source_timezone（明确固定UTC偏移）、property_defaults。禁止代码/eval、任意格式化属性访问、未声明转换、重复目标及defaults覆盖映射。scope由已批准过滤中的shop_key值固定，唯一键模板只可引用pk或已选字段。

Shop新包配置拟沿既有缺省语义显式声明status=active（AOS对象生命周期缺省，不冒充商城营业状态）、currency=CNY、timezone=+08:00；如业务需要其他值须走包/配置变更，不从本次源数据推断。此处只定义合同，不写当前安装或审批；新包准备与签名/安装升级下一波另行实施。

materialize_snapshot(rows,compiled,observed_at)只接收完整选列结果，要求字段集合精确、必填非空、唯一主键及唯一输出标识、过滤值一致，最多1000行；int拒绝bool/字符串数值，string不自动字符串化，timestamp只支持非负整数Unix秒、0为null。快照source_updated_at统一使用明确UTC观测时间，源createTime保留自身字段语义，不隐式取now或补造源事实。输出只含ot/source_pk/external_id/source_updated_at/source_timezone/is_deleted/properties，原始额外字段不透传。compiled持有不可变元组/标量，调用方仍须通过当前Owner和真实读返回做版本/授权检查。

验证使用当前P01映射加拟新增配置的合成副本，不更改旧包；证明11字段和明确defaults进入属性、0时间转换、观察时间稳定、错字段/类型/主键/过滤/模板/默认覆盖及缺配置拒绝。不进行真实源调用或写入。随后新包声明验证、独立占用提交及一次读取准备、原批次恢复、真实P01验收。
