# UQ5-B3b2 growth1.8候选冻结

2026-09-13，m1基线b0bd07fe，不push。

正式新候选：bundles/candidates/ecommerce/solution.ecommerce.growth/1.8.0，treeHash sha256:718548ad92a3715891b4b84060f0a2f22ad4baf6e492195573738e49c40ac8c4。旧1.7树保持2ba9ed424307ca1d4bf379656714705429a3efa93b9657d0a3976bd5fbd3a1b1。

87个基线文件不删除；仅bundle.yaml、注册entry及8个自身引用更新，新增projector、frontend HTML和manifest。六数字同事Profile等其他文件字节保持。24项注册=14导航/UI+10API；7增长模块及独立operations-base边界保持。UI只声明analyst及固定read，无command；请求ecommerce.workshop.read须安装锁实际授予，不能由候选自行放权。

候选差异/防覆盖/漂移拒绝/ManifestLoader/SDK贯穿及只读投影共23 passed，7项既有警告。候选实际SDK帧返回1 Case/1 Run fixture及executionAllowed=false；不是租户真实数据验收。AR2-7扫描1851，错误列表全部空。

该候选尚未构建镜像、签名或发布，旧主库/Host/签名安装保持。下一波：为growth1.8和当前niushop1.5配置受控构建器，真实OCI注册/心跳/固定读取/停止资格验证，产出新证据后再签名与UQ6部署。
