# BG00FC verification — 2026-10-01

## 实现与复审
新增issuer config复用既有私有JSON读取（16KiB、0700/0600、owner/no-follow/非阻塞、重复键/NaN拒绝），exact schema含scope且只接受orgId/projectId；database无密码/角色字段。返回已有IssuerProcessConfig，不复制进程/审批权威。
preflight要求预期scope等于私有scope，复验OS/外部OIDC配置形状、socket目录与路径未占用、私有attempt；仅通过connect_issuer_read_only读取身份/超时及118两触发器的目标函数/启用/类型/invoker/search_path结构。函数体签名、HBA、正式OIDC及部署审批不由此证明。
CLI复用consumer Parser/Once，无参数/缩写/重复/任意密码参数拒绝且不回显；--mode/--config/--preflight-org/project均显式。check只预检；serve先预检后有限循环。输出businessAuthorized=false，异常exit1，参数exit2；导入不加载Web main。

## 验证
RED session18682：缺config模块，exit2/0.43s。专项session24363：20 passed/7.83s/exit0。累计session23255：79 passed/16.25s/exit0，7已有warnings。git diff --check exit0。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_config.py services/aos-api/tests/aip/test_network_issuer_cli.py services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_cli.py services/aos-api/tests/aip/test_network_issuer_process.py services/aos-api/tests/aip/test_network_issuer_startup.py services/aos-api/tests/aip/test_network_issuer_application.py --tb=short --show-capture=no
```

真实临时文件/子进程check与idle serve/临时PG身份，前后Proposal/Event/Receipt计数相等，无attempt新增，socket退出移除。隔离PG停用guard后预检拒绝并finally恢复。旧消费者CLI/配置相邻回归通过；借用隔离fixture的API UID是未实际运行的独立UID，idle不是跨OS正向签发。当前真实库/配置/服务未变，无浏览器通过声明。

## 下一波BG00FD与风险
已查看apps/web/src/pages/s2/RuntimeNetworkPolicyPreviewPanel.tsx，该面板仅调用activation-preview；检索apps/web/src未见新增decision-attempts/activation-consumptions字面接线。此搜索只作路由线索，不证明全前端能力缺失。BG00FD复核网络配置产品链（Proposal→独立checker→Event→消费）现有通用页面/读取合同及断联对账，形成最小文件级接线方案后推进必要实现，不自造客户端审批权威。
正式OS/OIDC材料、HBA/签名来源、119–122部署/损坏启动载体恢复仍独立门；总业务deadline/网络失联上限、真实Event/八配置/Owner/Host与自然首链未达。当前真库只读、不读商城源/旧Run/manual run_definition/Provider/230L0、不push。
