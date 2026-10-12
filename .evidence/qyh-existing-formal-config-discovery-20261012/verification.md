# 既有正式配置入口定位

严格限定project/repo/API三已知根的.env/.env.local/.env.production/.env.example。实际2文件：repo.env和模板.env.example，8个所需OIDC/现有writer/新producer/runtime credential参考键均未发现；当前工具环境也无这些键。仅输出文件和键是否存在，不记录值、不打开引用credential正文、不复制Prime身份、不创建账号/token/OIDC或发布身份。

原limited HTTP实际需求为非local HTTPS issuer/JWKS及audience，不是dev默认issuer。此已知路径调查不能证明其他位置没有真实配置，也不能推定所有publisher来源都在这8个键中；既有独立发布来源仍需原路径。没有查看运行API全部环境，避免秘密披露。正式身份未建立，当前代码/角色部署或八台自然首链不因此成立。

两个已登记候选：当前原卷维护与正式配置接入；此为接入的有限必要调查，不把缺配置变为整个Goal停工。保持已问配置位置信息待答，不重复索要秘密、权限或旧裁决。无产品代码/数据库/配置变化、无单测镜像实现或重启。
