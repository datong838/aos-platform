# 登记恢复面板验证｜2026-09-13

基线6861693b。第1/6复核产品恢复入口和客户端；第2/6完善方案及exact请求/回读合同；第3/6接RegistrationPanel和安装详情，用户不填ref/key/etag；第4/6真实浏览器5173/apollo/assets选择97aeb2e7安装，新面板显示登记服务读取失败，刷新仍拒绝且无撤回动作；旧API尚未部署该接口，不算主库验收。第5/6五文件43项通过、tsc通过、diff检查通过；第6/6提交后直接修复真实安装详情证据类型不兼容。

测试覆盖精确请求、headers/CAS、错回执、结果未知不重发而用原对象GET回读、离线禁入、租户变化和迟到响应；既有AssetBundlesPage测试同时通过。日志/tmp/a0v-registration-panel-final2.log、/tmp/a0v-registration-panel-tsc-final2.log。UI无技术编号输入，不保存权威状态，提示成功只来自匹配回执；服务不可用与无权限不能算未登记。主库025、运行API旧版本，未进行真实撤回。

浏览器新发现：当前安装详情API实际200，但前端parseInstallationDetail报Installation event evidence.type is invalid；真实证据type为runtime_preparation。后端合法enum还包括preparation_reset、uninstall，前端只列dry_apply/verification/rollback。登记为下一波产品缺陷，禁止放宽为任意字符串。真实首链与八场景仍未完成。
