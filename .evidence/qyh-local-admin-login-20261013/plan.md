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

## 用户指定账号配置
用户直接指定本机真人登录名datong838与密码，并允许配置本机系统数据。沿同一已创建human UUID/realm，不新造第二真人、不重批恢复请求。用既有bootstrap管理账号的真实本机Keycloak管理API，将同user UUID用户名改为datong838，设置用户提供的密码并取消首次临时密码动作。用户密码只由仓库外0600私密输入文件读取；不得写命令/环境/日志/公开证据/Git。管理token仅在进程内，GET精确user ID/tenant/admin角色与client scope先验、PUT用户名/原reset-password接口，各有排他intent并失败后先GET对账，不假称本人登录。保留当前scope/org/project和角色、first/lastName，不改审批或AOS当前数据卷。原login handoff私密文件同步为用户指定账号；当前Public健康与页面验收后继续原AOS接线。

## 账号实际前检发现Tenant属性未纳入UserProfile
真实Keycloak GET原human UUID无attributes，当前默认UserProfile忽略未声明自定义字段；不能冒称token带正确scope或用allowDev回退。账号修改前停止，无用户名/密码写intent。修复仅本机qyh-local Realm：先GET原users/profile保留全部既有字段，新增org_id/project_id/markings的admin-only view/edit声明（用户账户页不能修改tenant），保留unmanaged禁用；验证该realm仅预期human账号，再原profile PUT/GET精确回读，原User PUT填固定org-org/dev-project/public+restricted并保持全其他profile与角色。每个profile/属性变更有排他intent/terminal，不重发未知状态。之后继续原用户名/密码配置，不改原AOS数据库/审批/业务运行。

## 原用户名编辑策略与精确续接
原UserProfile/tenant属性已经实际落账，用户名PUT明确400；密码reset尚未发出，不重跑已有intents。将纯HTTP帮助函数保留、主入口加main守卫供单次续接复用。先只读原realm.editUsernameAllowed和同human UUID；若原false且username仍qyh-owner，排他intent临时允许原username修改，原User PUT只改username，立即finally恢复原false，再原password reset与要求动作回读。不能扩大注册权限/增加管理员/人类用户，不改人类UUID/原审批/AOS库。每一步独立intent与终态回读，未知则仅对账。

## 用户指定凭据实际登录与原验证器自测
用户名/密码已由原Keycloak API精确落账，用户授权建立并测试本机登录。只在独立自测进程设置原OIDC验证器的公开issuer/JWKS/audience/client/tokenURL（不含密钥），读取仓库外0600用户凭据，原issue_password_token取得一次实际JWT；不打印/写token/password。原resolve_principal必须验证实际签名/固定org-org/dev-project/admin/public+restricted、sub同已建human UUID。跨org/project header和dev token均原函数拒绝；此证明凭据/原验证器能接通，不证明live API已接线或本人互动登录。测试后的原session仅用本次refresh_token logout，不登出其他会话；所有auth token仅进程内、不写AOS真库、Host/worker/Provider不启动。

## 用户名密码模式实际自测400与可选邮箱
原password grant明确400且无Token返回。真实GET user无requiredActions、姓名已填、邮箱未提供；原profile默认email对user必填，导入阶段忽略该约束不能证明登录。该本机唯一真人按用户要求仅用户名密码登录，不虚构邮箱或再索邮箱批准；仅qyh-local用户profile的email移除required，保留email格式validator和全部其他字段/tenant admin-only权限、注册关闭。原profile PUT/GET差异只允许email.required，之后新的r2排他login自测intent使用原函数，r1实际未获得session不重发未知结果。AOS源库/审批不改变。

## 实际AOS验证器所需sub claim修复
r2实际密码登录已获Token，原AOS必需sub校验拒绝；r2测试refresh session已原接口logout，不重发未知会话。仓库旧realm模板aos-api默认scope缺当前Keycloak basic，不能改JWT校验要求/手工补sub。只GET当前aos-api client与built-in basic scope，原默认scope精确添加basic并回读，其余scopes与admin限制不变。新r3自测意图与原签名/tenant/canary/dev拒绝/特定session退出必须全过；不影响live AOS配置。

## 显式有限时钟容差接线自测
r3实际签名Token缺陷已修复，仅被原iat拒绝，测试session确已logout。测得VM领先主机1.365s/NTP offset1.495s，独立qyh-oidc-clock-skew-20261013 Task实施原JWKS仅显式0..5/default0，原签名/必需claims/租户不放宽，当前本机自测显式2；新r4独立intent再次验证真实原登录/签名/claim/tenant/admin/markings与跨scope/dev拒绝，并仅登出此次会话。AOSlive配置未变，不修改系统钟或Source/Budget授权时间。
