# 隔离 PostgreSQL Ed25519 依赖验收

唯一m1写者，基线7708c858/AOS-001372；仅本Task目录、新测试镜像及独立容器/卷。没有修改现有库、恢复副本、默认部署/运行服务，没有授予真实Source/Host/Provider权限。

## 实际结果

- 原151恢复副本只读dependency RED：函数schema不存在，red.log保留。不是完整publication RED。
- 构建r1缺varatt.h失败；r2编译/安装成功但openssl CLI版本命令失败；补头文件和改用包元数据，严格-Werror保留。r3成功；r4增加pg_shdepend既存owner全类型依赖拒绝后重新成功。build-r1至r4日志均保留。
- 最终r4镜像sha256:a0eb61b312f90f7c5891afc088edc2824ae8eae1dd21ab8ba0e3ef78b1027eb8，来源基线sha256:73ab830fbe32945cf873ebc20ca0aceb532a73a3d4fda1684d1b4b9e0a965fe3。
- final实例aos-ed25519-test-31dccb3dc27e，colima-aos-a0v-test-only，network none、无端口、非privileged、独立同名-data卷仅挂载/var/lib/postgresql/data；原始attempt-r3.json保留身份。
- 最终完整原生19项通过，2.32秒，exit0，native-r4-final.log。RFC8032空消息公开向量、独立cryptography随机签名、二进制/NUL/中文、消息/签名/公钥篡改拒绝；错误长度及NULL非许可；2MiB及2MiB+1分别真实EXTENDED/EXTERNAL存储并核pg_column_size；同连接1000次失败后合法签名正常；READ ONLY成功；普通角色默认schema拒绝、仅schema grant仍函数拒绝、明确双grant才成功且全rollback。
- 安装前LOGIN owner与既存enum owner漂移均拒绝并rollback；schema/function固定owner、角色NOLOGIN/NOINHERIT无高权/member、PUBLIC ACL0、SECURITY INVOKER/STRICT/IMMUTABLE/PARALLEL SAFE/nonLEAKPROOF、probin/prosrc匹配、非重定位扩展原生catalog确认。
- source-hashes.json及runtime-r4-provenance.log记录源/安装/.so/libcrypto hash。PG16.14，build-dev/libcrypto3.5.9，runtime3.5.7；当前固定runtime已真实加载验证，版本差异不被隐去，也不推导其他镜像兼容。独立ldd报告的pfree/pg_detoast_datum_packed/toast_raw_datum_size为PG后端提供符号；真实SQL加载/调用通过才是运行证据，ldd单独不是验收。

## 复审与边界

现有独立路线督导提出超上界TOAST、同连接失败后恢复、schema/函数catalog与隔离容器身份及产物来源检查，全部补入最终测试和证据。代码复核：detoast前逻辑长度检查，EVP资源生命周期内不调用可能PG长跳转的API，正常路径释放EVP和复制输入；不含私钥/签名/SPI/网络/文件写操作。没有前端改动，浏览器验收不适用。

本Task只证明密码学校验依赖；verify true仅验证给定公开key，不能建立可信Source。正式root/permit/bootstrap、当前性/撤回epoch、全域映射、完整原caller锁序、一次publication COMMIT与consumer仍未实现/验收，原publication/b90/全Goal保持未完成。此隔离镜像不是生产部署授权。

最终独立route_supervisor只读回读r4源码/终结日志确认“交付范围内未发现新的重大阻断”，允许本依赖子Task收口；正式Delivery在AOS-001373，结果ISOLATED_SQL_ED25519_VERIFIER_NATIVE_19_PASS_NO_PRODUCTION_AUTHORITY，七强投影CURRENT。原publication已进入签名原文字节/重复JSON键及同事务稳定ID待签阶段调查；具体完整SQL实现仍pending。
