# 栖月汇本机真人登录入口

用户已明确选择建立本机管理员登录/审批入口，并本对话完成恢复审批，不再索取重复审批。复用仓库既有Keycloak26.0.2/RS256/JWKS/OIDC基础，与AOS权威数据卷隔离；不使用开发样例alice/固定密码/任意subject发devJWT。仅一名真人owner账号、关闭注册与其他角色，双租户claim固定org-org/dev-project；新身份来源和对话审批历史区分，不冒充已有企业外部OIDC。本人实际登录前不声称已认证。

第一阶段本目录bootstrap.py/plan.md：原colima-aos-extension上的精确镜像拉取与独立身份数据卷准备；Docker绑定127.0.0.1:18448，新资源名qyh-local-identity-20261013与qyh-local-identity-data-20261013，不使用/替换权威PG卷。Realm/client固定AOS实际origin，仅原password/code登录流程；管理初始凭据与human初始密码生成放仓库外私密0700/0600目录，不进env变量、参数、stdout、Receipt或Git；Docker通过私密realm/env文件读取。新secret目录/容器metadata查询不得打印密码/token。登录用户不由代理使用其凭据冒充，健康验收只公共discovery/JWKS。

后续独立文件级计划：正式用户登录页面/原验证器精确配置与只读API接入，所需代码须先Task/Lease/RED；此阶段不改业务服务、不启用Host、不授模型运行/商城/旧Run或预算执行。固定原prepared镜像缺失为当前实际依赖，执行一次可对账pull；失败分析当前handle与网络，不谎称登录已可用。已有审批approved3不回退或重批。Identity健康不等于AOS8台准备通过。适用浏览器需实际登录页面和租户/开发token拒绝验收后才能报完成。

## 首次启动内存故障后的最小调整
原VM内存3GB/Available21MB，Java build子进程被Killed并容器循环重启；本轮新身份实例已一次受控stop，原PGStartedAt12:25不变。仅保留失败身份容器并改名，保留同一新身份卷/Realm/人类初始凭据，不删除原身份、演练卷或其他容器；新启动候选的JAVA_OPTS_APPEND限定-Xms64m/-Xmx192m/Metaspace128m/CodeCache32m，容器memory768m并retry unless-stopped仅在有稳定health后启用，启动阶段restart=no以避免压力循环。所有密码只从原私密env复制到独立0600文件，不输出。用原signed镜像ID，监听同一18448，仅公共OIDC/JWKS/真人登录页面验收，不由代理登录human账号。

## r2 Realm导入路径诊断及r3修复
低内存启动已通过Java构建与身份库初始化；真实失败为private host文件不属于Colima共享路径，Docker-v实际挂成目录，Keycloak导入报Is a directory。保留r1/r2身份容器与同身份卷、记录schema已创建；不重放未知审批/业务操作。r3仅docker create无host realm bind，然后docker cp -a从本机0600Realm流式复制到固定身份容器路径，维持实际UID501读取；启动时若原错误JSON名空目录仍存在则精确改名保留而非删除。只允许empty-directory，否则拒绝；不改AOS数据/角色，原human UUID/凭据保持，私密文件不输出。最终必须公开discovery/JWKS和真实浏览器账号登录页验收。

## r3目录权限与r4同实例恢复
r3在启动Keycloak前对原空错误JSON目录改名被root-owned父目录拒绝，未执行Realm导入。所有身份server实例均停止，受控one-shot helper仅挂同一新身份卷，以root将空错误目录精确改名保留，import目录owner501:0/mode750、真正Realm文件owner501:0/mode600；server保持非root501。Keycloak尚未导入人类realm，因此在原私密Realm同userUUID/密码上只增aos-api client admin明确scopeMapping，保留fullScopeAllowed=false。文件Docker cp -a进入同一原stopped r3，再同一容器start一次，不创建替代身份卷/人类账号、不重发业务动作。helper容器保留、源卷不挂载。

## r4复制UID失配到r5原生写入
精确metadata读回原import父目录修复成功501:0/750；docker cp -a复制文件却实际为65534:65534/600，root helper的chown也被该文件UID映射拒绝。保留部分结果，不重跑helper。r5只用同新身份卷的501:0一次helper，将原不可读文件精确改名保留为非.json文件，再通过Docker受支持stdin stream把本机私密Realm写入umask077/当前501新文件，不把密钥放参数/env/输出。该helper退出后同一stopped服务器start一次；源AOS仍不挂载/不变更。
