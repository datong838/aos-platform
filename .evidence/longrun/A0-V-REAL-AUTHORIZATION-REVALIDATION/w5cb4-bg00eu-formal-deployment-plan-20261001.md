# BG00EU 正式部署只读盘点

AOS-001009/m1@74ba11ac。复习 BG00co OS隔离军规、BG00cm真实库门、BG00ET显式入口及231首链依赖。不新增业务实现，只新增本plan与verification。

核验：当前m1/强一致上下文；宿主已登记AOS账号与进程UID、已知启动配置；根.env及services/aos-api/.env与当前执行器环境的OIDC/入口键存在性（只输出set/unset，不输出凭据）；AOS_BUNDLE_ROOT路径是否存在；当前恢复PG数据库/迁移/角色LOGIN和权限、HBA auth方法及精确org-org/dev-project网络Proposal/Event/Receipt行数，显式READ ONLY；监听端口。源码检索产品入口对issuer/consumer的真实调用，不以函数存在推断接线。

对无进程/无路径的OS ACL不伪造正向结论；仅登记缺证，扫描范围明确。禁止读取商城源、密码文件或JWT；不创建账号/容器、不迁移、不授予角色、不启动服务/Host/worker/Provider、不重发。测试无新增逻辑，专项/累计使用上波74通过为历史，不冒充本波新验证。浏览器无UI修改，本波不作页面验收。

输出矩阵按当前证据/缺失authority/可独立研发下一步区分；本波代码和文档精确提交、Receipt、CAS、AOS/Prime同步。
