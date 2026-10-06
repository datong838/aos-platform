# 容量Source数据库签名边界：独立验签依赖方案

构建r1实际RED：PG16将VARDATA_ANY/VARSIZE_ANY_EXHDR定义在varatt.h；只补显式头文件引用，继续-Werror，不削弱输入或权限门。r2独立日志保留原失败。运行测试只在新隔离实例进行。

r2编译与安装成功，版本采集命令因基础镜像没有openssl CLI失败；r3改用apk info采集实际libcrypto3/openssl-dev包版本，无新增运行依赖。

收口复审补强：只枚举表/函数/schema不能覆盖type、tablespace或default ACL等角色依赖。安装前增加pg_shdepend角色依赖检查，拒绝既存owner拥有或获授任何集群登记依赖；增加既存type owner原生负例，r4重新构建并全新实例验收。该收紧只影响新扩展安装，不修改现有库。

基线7708c858/AOS-001372，主publication原Task仍ACTIVE，本独立Task gt-capacity-sql-ed25519-20261006仅覆盖实际缺失的数据库密码学校验依赖；原用户已授权Model评测设计/隔离实现。由唯一m1施工，不部署现有服务/库，不开启真实Source/Provider/Host，不新Goal。遵循231-4权限/兼容迁移与原publication“不能依赖客户端verified boolean”门。

## 当前证据与取舍
实际完整151恢复镜像PG16.14/Alpine3.24.1具有postgres.h及libcrypto.so.3，未有匹配Ed25519验签SQL函数；pgsodium不在可用扩展目录。pgsodium官方支持detached验证但完整包有server key管理/多种加解密/密钥表等额外能力。本步骤只需要无密钥状态的verification，选择PGXS单C函数调用现有OpenSSL EVP Ed25519，不实现签名算法、不借plpython3u任意解释器、不改变签名协议。OpenSSL官方要求PureEdDSA one-shot EVP_DigestVerify及NULL digest，函数逐项检查返回值并释放资源。

来源：https://docs.openssl.org/3.0/man7/EVP_SIGNATURE-ED25519/ 、https://www.postgresql.org/docs/16/xfunc-c.html 、https://www.postgresql.org/docs/16/extend-extensions.html 、https://github.com/michelp/pgsodium 。只以本次实际PG执行证明实现，文档不是运行证据。

## 文件、接口与权限
- services/aos-api/postgres-extensions/aos_ed25519/{aos_ed25519.c,Makefile,aos_ed25519.control,aos_ed25519--1.0.sql,Dockerfile,README.md}。
- scripts/tests/test_capacity_sql_ed25519.py：原生SQL验收，固定colima-aos-a0v-test-only、仅新独立none-network/无端口/独立卷实例和新增image。不绑定现有Source/恢复实例、不改dev-compose、不删除卷/日志。
- .evidence/gt-capacity-sql-ed25519-20261006/：计划、RED、编译/原生验证和来源hash。

唯一接口 aos_ed25519.verify(signature bytea,message bytea,public_key bytea) -> boolean；长度signature64/key32，message<=2MiB，错误/过大输入false，NULL由STRICT返回NULL，后续SQL门必须IS TRUE。支持原始字节含NUL/UTF8/TOAST，不JSON重编码、不做canonical hash或purpose判断；原Source必须从受控permit/root读取公钥和签名原文，并验证协议purpose/目标/期限/批准/当前性，不能把该true当业务授权。无私钥参数、签名函数、SPI/数据库写入、网络/文件/配置访问；SECURITY INVOKER非LEAKPROOF、不安装通用sign接口。安装script显式REVOKE全部PUBLIC schema/function权限，不能自动grant aos_runtime/issuer；将来152独立publication owner最小grant须另做严格catalog与binary来源审计。

## 隔离实现与验收顺序
1. 受邀原路线督导只读复核本计划；准备RFC8032/独立cryptography签名，原恢复151只读SELECT缺函数为真实dependency RED（非完整Source RED）。
2. 固定实际现有image sha256为测试构建base；仅新镜像build-stage添加编译依赖，runtime拷贝.so/control/SQL，使用PG_MODULE_MAGIC/PG_FUNCTION_INFO_V1。不改现有image；记录base/compiler/OpenSSL/.so/源文件hash，不把mutable镜像tag当固定身份。
3. 新no-network无端口独立卷PG实例只做pure verifier；首次SQL安装由隔离bootstrap admin，不授生产安装。RFC已知向量、实际Python签名/错key/篡改message/signature、空message、NULL/长度/上界/压缩和未压缩TOAST、binary/NUL/中文canonical bytes；反复调用失败后合法验证仍正常。
4. 实际普通NOLOGIN测试角色默认schema/EXECUTE拒绝，测试仅明确grant后可用；PUBLIC ACL0，无写/SECDEF，READ ONLY可验证，原SQL状态/业务表不增加。签名校验true仍不授Source/账户映射权利。
5. 编译警告/内存释放/固定接口/来源及方案复核；Task只交付验签依赖，不收口fullSource/publication/Model/首链。下一步完整bootstrap/permit/signedSource契约和全SQL/锁图冻结，再原signed input完整publication RED/COMMIT/consumer，缺正式外部授权时仅test-only机械验收。

失败保留attempt与资源，未知结果只读对账；不为重试覆盖旧SQL/容器/日志。任何实际部署或已有库加载仍需独立正式门。本步骤是既定数据库防绕过边界的隔离实现选型，不授权新的生产密码学组件部署。

## 独立路线复审修订
原route_supervisor只读审阅确认隔离选型符合范围，提出三项编码前约束，全部采纳：对三个varlena先toast_raw_datum_size（含VARHDRSZ）核逻辑长度，常量界无加法溢出，之后才detoast；所有可能PG ERROR的输入处理在EVP对象创建前完成，创建到释放间不调用PG API/interrupt/error，detoast副本按PG_FREE_IF_COPY释放而不释放借用指针。schema固定aos_ed25519、control不可重定位且非trusted，固定NOLOGIN/NOINHERIT无高权/member的aos_ed25519_owner只拥有schema/唯一C函数，安装前既存角色属性/对象/ACL漂移拒绝；非SECDEF/default PUBLIC全撤权。编译与运行PG/OpenSSL版本、动态依赖、最终image与.so及安装文件hash均实际记录。本复审不授生产部署/业务权利。
