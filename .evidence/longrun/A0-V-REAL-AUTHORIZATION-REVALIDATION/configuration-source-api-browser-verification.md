# D2d-4c 来源目录真实API和浏览器验证

2026-09-14，运行API代码0b02e403。原a0v_product_controlled_api.py check通过，保留niushop-1.5原13版本根与UI只读身份；后台Host/cron/自动逻辑/迁移均关闭，显式清除配置登记身份引用，stage开关0。

仅TERM旧API64738并同启动器启动72063，/v1/health返回ok。独立Host6606启动时刻仍2026-09-13 10:42:36，三OCI名称/ID仍a926…/b8a3e6934d38、5c46…/79f10db1661a、a8ab…/13aebdbfa46c。没有停用、迁移、登记POST或重启Host。

IAB /apollo/assets，97aeb2e7-59ba-40f6-89a3-fb0293bc0497：点击刷新配置来源后出现职责计划 ecommerce.business-investigation.readonly 版本2（responsibility-plan-63c82d2a75614e1b95f1），运行策略a0v-ecommerce-runtime-policy-v1版本4，选择框可用。原配置1版本1仍显示当前绑定，原运行enabled/ready、epoch3/binding4保持。只读目录链路已实际验证，不代表登记执行成功。

memory-status全部强投影CURRENT，memory-validate GREEN；authority仍AOS-000573，AR2 fixture-only结论不变。

下一波D2d-5：036至038最新真实主库备份/克隆迁移演练、最小权限登记身份验证；演练通过后才部署主库新增结构。独立Host切换仍需先完成既有恢复/替换链路，禁止直接重启丢失当前OCI所有权。
