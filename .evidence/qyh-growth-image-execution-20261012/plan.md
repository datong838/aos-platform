# 原Growth镜像真实执行诊断
基线6cfbf68f3/AOS-001908，原源码后继候选已冻结。已登记候选一正式登录/publisher来源待答；候选二原构建器本机隔离镜像诊断已授权、安全独立，选择二。
新增仅本Task目录diagnose.py/结果/日志，复用原_build_image和_require_isolated_engine，输入上Task sourceTreeHash精确绑定。原build全流程有签名qualification与四包输出，本波只使用其原镜像封装函数做诊断，不能冒充全构建验收。工作目录Task内，镜像tar保留不提交，旧源和旧包不改。
本地缓存base/SDK生成镜像，networknone/pullfalse；镜像运行readonly根目录、networknone、capdropALL、no-new-privileges、512M/1CPU、UID65534、无挂载/无端口。有限原注册及阶段评测模块导入检查，结果无论exit0或非0均原样保留，错误为失败；后续按实际缺口准备最小修复方案。不签名/发布/连接生产库/Host/Provider/重放Run。检查容器exit/无挂载、source1695原包不变后收口诊断。

## 实际RED后的最小修复方案
原镜像注册PASS但StageEvalProof实际导入ModuleNotFoundError:pydantic，容器exit1，无外部效果。新增同Taskrepair_image.py：从原services/aos-api/uv.lock读取pydantic依赖闭包5个原精确版本/wheel hash，选CPython311-musllinux-aarch64或通用wheel，下载只锁中URL、SHA256逐个校验；不解析最新版本、不复制macOS虚拟环境、不改全局依赖。构建前下载到Task wheelhouse，构建networknone/pullfalse，离线pip require-hashes/no-index/no-deps安装。复用原生成Dockerfile/SDK/源码，新增COPY wheelhouse和RUN离线安装，其他原权限保留，pycache不带入。新镜像实际原StageEvalProof两种policy类型/错误类型/布尔revision/accepted-stage未接线保护/全部原Growth模块导入验证。只独立候选镜像，不改原冻结builder、不签名/安装；缺依赖真实失败保留。本波证明隔离修复配方，正式通用builder改动要下一已登记方案和独立Task。
