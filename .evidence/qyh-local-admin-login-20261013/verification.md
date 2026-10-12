# 本机身份服务第一阶段实际验收

用户已授权建立本机管理员登录，并明确本次恢复审批无需再点确认；审批approved3保持。复用仓库固定Keycloak26.0.2当前镜像，真实digest cde8d7fff48622d7bff959ea2a98e945ae8a7ccb0117b44858de77243b96231e，非企业身份或厂商签名认证声明。

现有colima-aos-extension DNS坏链接导致pull RED，经独立DNS Task修复；同镜像拉取成功。r1虚拟机3GB/Available21MB使Java build被Killed，自身新服务一次stop保留，原PG12:25启动时间未变。r2低内存已初始化独立身份库，但非共享host文件bind成目录导致导入失败；r3串流cp后父目录root-owned改名拒绝；r4父目录修复成功但-a复制UID实际65534且chown被拒绝，部分状态保留；r5通过原生501进程从私密stdin写0600Realm，保留旧错误目录/文件/容器，无未知业务重发。

实际最终同容器db1446eed5db48cf75e524827775b1822f859a5c14d300b2e5349df67454acfa Running/restart0、独立qyh-local-identity-data-20261013卷、仅127.0.0.1:18448、非root501:0/768MiB。真实OIDC discovery精确issuer与RSA签名JWKS成功；真实浏览器登录页用户名/密码字段可见。仅在healthy后设unless-stopped。未使用人类密码/Token登录、未输出密码、未改AOS角色或数据、未开Host/worker/Provider。所有初始凭据仓库外0700/0600，首次人类登录要求改密码。

限制：这是独立本机身份服务与真人登录页，不是AOS登录/权限操作完整验收；AOS仍原只读dev预览，登录与API配置/操作界面需下一独立文件级接线。仅一真人新账号及固定tenant claims，不复用原alice或默认样例密码，范围固定AOSorigin且admin明确scopeMapping。没有把这次过程称八台可见、配置通过或经营首链。

下一主线：原AOS OIDC验证器精确接入当前本机公钥/issuer/audience、前端实际登录/退出/tenant读取、本人管理员权限的受支持Enrollment及受限控制入口；先方案/Task/Lease/RED，保留原默认正常功能和用户22改动。已有人工审批不重复索取。随后current runtime preparation/apply/verify/配置/资源→八页→自然首链。全Goal持续active。

## 用户指定账号实际配置与自测闭环
用户指定datong838及密码，仅本机仓库外0600文件读取，原Keycloak admin API在同一human UUID下更新；tenant profile声明admin-only、原email仅本机可选而非虚构邮箱、用户名immutable策略临时恢复原false、原reset-password204、admin角色保留。旧模板client漏basic使sub丢失，原built-in basic配置补齐，不放宽JWT必需字段。测得VM/host1.365s偏差，独立生产容差Task显式2/default0边界测试35PASS；实际r4真实token与原AOS verifier签名/sub/admin/markings/双tenant正向及cross/dev负门通过，单次自测sessionlogout。仅凭据自测，不声称本人互动登录。AOS API/Web接线仍未完成；原approved3不变、不重批，秘密和tokens未进公开证据/Git。
