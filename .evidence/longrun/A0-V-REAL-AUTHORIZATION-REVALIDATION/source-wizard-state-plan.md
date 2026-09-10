# 向导配置状态与探针运行位置

基线dbd8c677。参数修改时清空旧发现结果和成功消息；提交期间fieldset禁用，提交handler同步ref防双击。SSH端口从固定22改为输入。当前probe实际在API主机运行，必须只接受runtimeMode=direct，不可把agent/worker配置偷偷用本地连接测试。服务器先查props模式再开连接，前端创建前说明限制；不替用户更改选择。agent/worker真实派发作为后续功能，保持不能假测成功。

文件DataPage.tsx、source_connection_probe.py、探针测试。验证agent/worker/missing模式均不建立连接，direct正常；前端tsc。不访问真实源、不重载服务，完整交互和agent/worker派发未完成。
