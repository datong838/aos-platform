# BG00EX verification — 2026-10-01

## 实现/复审
既有私有JSON读取仅提取成_read_private_config，保持O_NOFOLLOW/dir_fd/O_NONBLOCK、0700/0600/owner、16KiB、fstat和重复键/NaN规则。API新配置载体不含DB/token/tenant字段；AOS_NETWORK_CONSUMER_API_CONFIG缺失返回None，显式错误固定CONSUMER_API_STARTUP_BLOCKED。复用Endpoint与ApplicationConfig，外部OIDC配置正确才装配。
main.lifespan只新增4行：先清空，try中在_lifespan_body前加载，finally先清空再原runtime cleanup。未配置原行为不变；启动加载不连接socket/DB，不创建attempt，不启消费者或其他业务执行者。没有改.env或当前实例。

## 测试
RED session10384：缺模块，exit2/0.52s。专项与原私有文件回归session60924：25 passed/4.53s/exit0。累计session29184：53 passed/15.26s/exit0，7已有warning。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_consumer_startup.py services/aos-api/tests/aip/test_network_consumer_config.py services/aos-api/tests/aip/test_network_consumer_cli.py services/aos-api/tests/aip/test_network_consumer_application.py services/aos-api/tests/test_health.py services/aos-api/tests/aip/test_aip_provider_health_main_startup.py --tb=short --show-capture=no
```

真实私有文件验证exact schema/危险字段/权限/UID/相对路径/外部auth拒绝；生命周期body/cleanup替身仅证明启动顺序与清空，不代表当前正式启动。既有真实CLI/配置PG、HTTP身份、健康/相邻main startup回归通过。无UI改动，browser不适用。git diff --check exit0。

## 未完成/下一波
当前库118只读、119–122未部署；正式OS/IdP/ACL/签名配置来源未证明，真实首链未完成。已向用户异步询问已批准身份/部署材料位置，不索要密码/Token，不以等待中断独立研发。
BG00EY推进独立issuer的产品调用通道，复习既有签发IPC/持久attempt，复用底层私有传输，不复制审批权威；先方案后编码。消费者端的正式装配验收等材料到位后独立进行。启动载体异常仍须独立恢复门，不借本波改实例。不push，不读商城源/旧Run/manual run_definition，230L0挂起。
