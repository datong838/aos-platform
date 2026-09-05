# AOS 独立运行开发环境

只使用独立profile `aos-extension`，不修改Docker Desktop。配置依据Colima0.10.3、Lima2.2.0现场验证。将本目录配置部署为本机profile配置后启动：

```sh
colima start --profile aos-extension --activate=false --mount none --ssh-config=false --binfmt=false
python3 deploy/dev/extension-runtime/verify_environment.py
```

`--mount none`必须显式保留，防止默认home挂载。每次Docker命令指定`--context colima-aos-extension`；不切默认context。只停止此VM用`colima stop --profile aos-extension`，不要停止共享Docker。

专用daemon必须保留userns-remap。Docker29启用containerd-snapshotter时与userns冲突，所以本独立空环境禁用该存储特性；不对已有引擎执行该变更。

验证脚本只使用本地固定镜像、不拉取、不联网、无挂载，探针自动删除。初次镜像从已有Docker导出导入，验证后固定image config digest。环境通过只代表运行测试前提，不代表领域制品、监督器、IPC、注册、持久绑定及全安全profile已实现。

参考：https://colima.run/docs/configuration/ 、 https://docs.docker.com/engine/security/userns-remap/
