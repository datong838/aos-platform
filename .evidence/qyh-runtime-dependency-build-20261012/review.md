# 原构建器运行依赖闭包复核
原Runtime builder已接入源码AST导入检测、冻结5wheel版本/URL/hash、限时限量下载和缓存hash拒绝，Docker仅离线require-hashes/no-index/no-deps安装；SDK-only包旧依赖锁保持。包源码/SDK复制排除pycache；运行镜像只读根/无网/无挂载/非root有限模块导入门在原_build_image内，错误阻止BUILD_GREEN。不是仅新增诊断脚本。
每包artifact lock与本包image-index dependencyLockHash精确绑定；顶层hash变为各包映射摘要，新增dependencyLockHashes，不能继续用SDK-only摘要冒充Growth锁。SBOM保留版本/hash并拒绝已有同名不符记录，仍幂等。
新5项原RED皆失败，扩展后新8项及原builder/UI/current/Growth112/113/QYH恢复/签名相邻共45PASS/0skip/7既有警告。一次扩展测试fixture缺完整manifest失败保留，改用已冻结原真实manifest/source复验；未弱化ManifestLoader或校验。
实际原更新_build_image离线构建两个包：Growth1.13.1的42模块、Niushop1.23.0的3模块，均容器真实exit0且无挂载/无网/只读；sourceTreeHash和1695原候选/发布文件前后不变，结果绑定当前builder/spec字节hash。无需浏览器：本波没有切运行服务。
限制：模块导入仅闭包资格，不授Host/Provider或经营动作；新的完整四包source/version选择、全部构建与独立发布/当前安装/正式登录/八页面及自然经营首链均未验收。旧注册-only qualification/已签包不能因此自动变为业务GREEN，未覆盖原签名或旧数据。22用户修改保护（仅本Task原builder一个tracked文件改变）。
下一已登记安全项：最新四包继任source profile和新Growth1.13.1原构建/新评测资料绑定，随后实际新四包build/qualification；正式登录/publisher接线仍待原配置来源，不能借dev身份。
