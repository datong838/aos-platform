# 来源选择草稿与控制合同兼容验证

2026-09-12，基线40800cb9。PipelineControlContext承载共同的租户、图、安装、包、真实源配置、资产引用、读取预算及时间约束；原PipelineRuntimeControlDraft保留其schemaVersion与SourceSelectionRevision引用。新增PipelineSourceSelectionDraft不含自身引用，只能prepared/readOnly=true，不是批准记录。

RED：4 failed/39 passed，来源选择类尚不存在；GREEN：控制合同、资产解释器和源配置版本共73 passed，10.93秒，7项既有警告。重构前记录的固定fixture摘要sha256:9b91cdf86f2ce473c33b8e90f36ccf2c68b58d298fa20c80f70238563668f77b在重构后不变；原JSON往返、用途、嵌套冻结、类型/预算/时间拒绝全部保留。新草稿拒绝自引用、approved、非只读及不合法预算。

AR2 ar2-7闭包1792/158/93，五类错误空；diff检查通过。未应用迁移、未追加审批或控制记录、未改变运行权限、未读取业务数据。下一波按照source-selection-persistence-plan.md完成不可变历史表及独立PG隔离/外键/不可变测试，再实现当前权限Owner和正式执行接线。m1串行、不push、230 L0挂起。
