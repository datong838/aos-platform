# 独立运行目录真实读回

部署代码 cfad7903。原 controlled API 959e4788 进程 exact command 核对后正常停止，新 API 18181 启动。沿用现有受控 profile；preflight sourceCalls=0/runsCreated=0，productionWebIdentityComplete=false，所以仍是本地诊断环境，不是生产发布。

实测 health 200；栖月汇 org-org/dev-project 目录 200、no-store、count=0、dataCutoff 有当前安装锁截止时间；隔离 dev-org/dev-project 200、count=0、dataCutoff=null；匿名 401。原始响应保存在 runtime-workshop-catalog-live-readback.json。

安装97aeb2e7-59ba-40f6-89a3-fb0293bc0497保持 active revision5 / ready，generation3a445eee-aa28-4459-9e5a-f12a806a94b1、epoch3、binding revision4、enabled=true/fence=false；配置721433ba-5256-4b12-9043-0bcfab658bf0@1，UI仍null。独立宿主 PID6606 连续运行约7小时29分，未重载。

空目录与当前签名包无 frontend 相符，不能解释为八工作台已经可用。未执行 UI 调用、业务 Run 或 cutover。下一波继续包内只读业务端口与 UI 调用权限技术接线，前端包交付后才可产生入口；首链、八场景和业务观察仍未完成。
