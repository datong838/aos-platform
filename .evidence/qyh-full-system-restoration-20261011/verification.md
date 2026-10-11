# 历史卷加载检查点（完整恢复Task仍ACTIVE）

2026-10-11：fresh647表完整备份、globals无角色密码、原hba/config保存，第二份字节校验副本通过（不是独立第二时间点备份）。原prepared容器正常停止后，因Colima未挂载主机配置路径，首次run退出125。inspect证明目标不存在；没有重放已提交LOGIN。采用create→cp无密码连接规则→start，挂载同一aos-qyh-history159-prepared-data-20261011卷，集群7695302940039200809/schema159精确相同。原prepared容器保留stopped；原092/当前preview与所有备份保留。

加载后647表逐表指纹等于加载前；随后只有public.meta_org一行name/updated_at按新CAS更新为栖月汇商贸有限公司，org-org/dev-project标识与行数保留。新增受限LOGIN：NOINHERIT/NOSUPER/NOBYPASSRLS、仅成员aos_runtime；密码仅private0600。网络仅本机18446、SCRAM限定该LOGIN、aos_app网络连接实测拒绝。维护Unix本地权限仍保留，不冒充外部正式身份。

新增scripts/a0v_qyh_restored_http.py目前是只读接入核验入口，**没有serve命令**。身份漂移/schema漂移先拒绝；实库回读栖月汇647表/135安装/130配置/126binding且enabled0、有限LOGIN通过。专项及签名/候选相邻测试22/22。首次9项RED为缺少新增模块；首次实库SQL失败因为误用了meta_project，按真实meta_workspace修正；这些失败均在只读阶段，无数据库写。脚本private文件要求本UID/0600/非symlink。

复审：不放宽原preview入口、身份/预算/ready/catalog门；不启Host/worker/Provider、不PublishRegistry/安装、不读商城源/重放未知旧Run。新增当前包本地签名另由Task qyh-restored-current-signature-20261011验收，签名不是运行权限。

完整恢复尚缺：现有发布坐标与旧签名来源兼容处理、当前安装与有效配置、实际API/Web接入、栖月汇租户浏览器和8页面读交互验收。当前运行API仍原preview，不能把历史卷接通或名称恢复当系统完成。全恢复Task/Goal保持ACTIVE，无Delivery/complete/blocked。
