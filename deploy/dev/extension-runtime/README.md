# AOS 独立运行开发环境

只使用独立profile `aos-extension`，不修改Docker Desktop。配置依据Colima0.10.3、Lima2.2.0现场验证。将本目录配置部署为本机profile配置后启动：

```sh
colima start --profile aos-extension --activate=false --mount none --ssh-config=false --binfmt=false
python3 deploy/dev/extension-runtime/verify_environment.py
```

`--mount none`必须显式保留，防止默认home挂载。每次Docker命令指定`--context colima-aos-extension`；不切默认context。只停止此VM用`colima stop --profile aos-extension`，不要停止共享Docker。

专用daemon必须保留userns-remap。Docker29启用containerd-snapshotter时与userns冲突，所以本独立空环境禁用该存储特性；不对已有引擎执行该变更。

验证脚本只使用本地固定镜像、不拉取、不联网、无挂载，探针自动删除。初次镜像从已有Docker导出导入，验证后固定image config digest。环境通过只代表运行测试前提，不代表领域制品、监督器、IPC、注册、持久绑定及全安全profile已实现。

签名镜像联合验收需要真实 RepoDigest，不能用虚构摘要或放宽缓存校验替代。允许在本专用 VM 中获取官方 registry 测试辅助镜像，记录实际 digest 后固定使用；仅本机回环 18433 端口、临时存储、无宿主目录挂载，不用于发布业务制品。它不是领域 runtime；领域容器仍断网且 pull=never。测试镜像仅向此本地临时 registry 推送/读取，不向公网推送；测试后删除精确容器和测试标签，保留既有镜像及 PostgreSQL。该环境准备不构成任何业务发布授权。

现场补充：专用 VM 的 resolv.conf 指向未安装的 systemd-resolved，公网辅助镜像获取失败；未更改共享宿主网络。离线联合测试改用测试目录内只读静态 Registry V2 fixture：从 docker save 诊断镜像构造 OCI manifest/config/layer 摘要，Python 标准库仅提供 GET/HEAD，不接收上传。服务运行在专用 VM 临时容器、回环端口，领域镜像由本地摘要读取，实际业务容器保持断网。此 fixture 不是生产 registry，实现不能进入平台服务。

参考：https://colima.run/docs/configuration/ 、 https://docs.docker.com/engine/security/userns-remap/
