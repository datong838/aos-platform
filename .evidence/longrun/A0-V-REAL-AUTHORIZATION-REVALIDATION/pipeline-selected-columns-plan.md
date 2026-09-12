# 来源选择前置：源端字段投影

2026-09-12，基线ad51c4b6。来源选择Owner设计核对时发现JdbcConnectorRuntime.read_rows只有SELECT *；ec_source_adapter在数据离开源库后清洗，不足以满足Niushop包的PII_DIRECT不出库要求。P01映射明确排除site_tel。因此先补通用源端字段投影，为后续Owner执行批准的字段范围提供实际查询能力。

## 本波文件与最小修改

- services/aos-api/aos_api/jdbc_connector_runtime.py：为read_rows追加可选columns参数，不改变既有省略参数的调用；显式columns必须是非空、无重复、最多100个普通SQL标识符的list/tuple，不允许星号、表达式、字符串容器、注释或动态SQL。显式字段读取必须给出严格整数limit且1..1000，禁止None/布尔/浮点。查询仍使用现有只读事务、等值参数化条件、原游标语义和连接资源生命周期。
- services/aos-api/tests/test_jdbc_selected_columns.py：先红后绿，检查真实生成SQL列清单及参数；非法输入在任何数据库调用前拒绝；只读事务与异常回滚沿用原实现。fake DB只验证查询构造和拒绝边界，不计真实业务完成。

不从HTTP暴露任意字段读取，不把用户传入columns当授权；后续SourceSelection Owner必须从已安装、hash钉住的映射/Schema/脱敏资产解析批准列，再传给此低层方法。本波不自动更改旧图、不启用P01、不读真实业务行、不新增连接权限。现有默认全列接口保留兼容性，不宣称旧通路已满足PII不出库。

## 验证与下一波

运行新增投影、现有JDBC运行时/私有连接/EC SourceAdapter相关测试，AR2闭包和diff检查。通过后持久SourceSelection仍须绑定tenant、source配置、installation/generation、固定方法、平台/店铺与允许对象、包资产和当前权限，再让P01走此投影通路；不得直接在图上设置live绕过Owner。
