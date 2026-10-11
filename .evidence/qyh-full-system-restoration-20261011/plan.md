# 栖月汇电商域全系统恢复执行方案

2026-10-11用户明确授权今天恢复栖月汇租户全AOS系统和数据卷、全量重启及纠正偏离电商域配置。唯一m1 thread；原current159维护Task保留拥有当前preview，当前已恢复名称但无历史data，禁止拿该名称检查点当整系统通过。

## 原数据卷加载
固定prepared container9e8e903010304d33a801065e96c38693c9cbdc7687b7fd35a76e2fe8dbb7ae82/image7e7db...，namedvolume aos-qyh-history159-prepared-data-20261011/database aos_meta_head/cluster7695302940039200809/schema159；原全647表恢复与roles/ACL/sequences已独立验收。再次private0700/full一致backup0600与第二校验副本、全表fingerprints/权限目录/配置备份、before/after/零其他活跃连接核对。原092/原preview/所有备份和卷保留。

先只读准备独立安全transport：新有限LOGIN(role qyh_restored_api_login)仅NOINHERIT/NOSUPERUSER/NOBYPASSRLS/成员aos_runtime、不授owner或直接表权限；私密passfile，不进args/env/日志/receipt。原hba/config保留；新只读hba指定此LOGIN/SCRAM、host loopback18446，无其他host用户/不使用trust暴露。维护窗口先停原none-network prepared容器，确认无进程并占用隔离网络端口后，新容器 qyh-restored-pg-20261011 使用同一数据卷与只读hba；不能两进程挂同PGdata；旧容器保留stopped，无rm/删卷。

加载后回读原cluster/schema/647table fingerprints/roles/权限/命名卷、端口与启动时间。恢复卷org-org的一行name按fresh metadata CAS恢复栖月汇商贸有限公司，不改变租户id/workspace/其他业务数据。新增LOGIN属于明确维保transport，不能作为正式Owner/业务权限证据；API正式身份/OIDC仍沿原门。

## 当前包、安装与API/Web
使用新core1.4.3+platform1.23.0+Growth1.13.0+operations1.2.0实际资格产物，旧core坐标不覆盖。签名入口已核验但未签；新local候选签名也不自行授正式Root/安装/运行。原产品resolve/lock/approve/apply/verify/configure及currentSource/Owner授权逐项对账；恢复Canonical407资源与ef5原历史/899旧12Run分离，旧unknown效果不重放或fake retirement。

新增独立scripts/a0v_qyh_restored_http.py与专项tests，复用原签名/current release/有限LOGIN/OIDC/worker关闭，精确目标和当前schema/generation/tenant门，先RED再最小实现。原preview入口不改；不要更换旧常量绕过门。若旧配置预算expired、binding disabled，不能直接改enabled/fence制造8目录绿。八入口隐藏的原产品行为需按产品/技术方案解决当前安装/configuration/真实resource准备，而非改test结论。

最后维护时序PG→最新m1 API→Web，真实浏览器栖月汇组织选择/默认工作区、8页面与核心只读交互、签名/安装/禁入/canary证据；保留可查看浏览器。运行Host/Provider只在正式身份/Owner/8config/current审批预算完整后开启。全Task仅到真实验收才Delivery，局部checkpoint不宣称完成。

## 未知与回滚

2026-10-11加载实测修订：Colima未挂载本机/Users配置路径，原docker run退出125；只读inspect证明目标不存在、原容器已正常停止。限定LOGIN已完成且不重放。改用docker create同一命名卷、docker cp无秘密hba到容器root拥有文件（postgres仅可读）、docker start；不依赖主机bind、不改变原卷配置。创建/复制/启动各自记录intent与terminal，失败只读对账。
每次操作intent/terminal。未知只读核对，不重试写；没有运行记录不代替证明。新transport失败先停新候选，不删旧容器/库/卷；原preview仍维持原identity和数据。恢复历史卷不改变original092。API登录/运行门失败只限制该动作，继续安全恢复主线。
