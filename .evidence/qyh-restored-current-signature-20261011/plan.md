# 栖月汇恢复当前包签名方案

依用户2026-10-11全系统恢复明确授权，使用已有实际build与qualification精确产物，为core1.4.3/platform1.23.0/Growth1.13.0/operations1.2.0生成独立本地Ed25519候选签名。新state位于aos-recovery/.aos-qyh-core143-signing-state-20261011-r1，签名前不存在；既有签名、旧core发布坐标与原库均保留。Task qyh-restored-current-signature-20261011同一线程单写，与全恢复Task范围分离。

使用已测试scripts/sign_ecommerce_qyh_recovery_candidates.py；不更改生产代码。写前保存intent，命令终止后独立进程核验4包签名/ReleasePolicy/hash/8模块；旧build保持无持久签名。本地trust root不作为正式Owner或执行权限，不Publish、不安装、不启Host/Provider/worker、不读商城源、不重放旧Run。错误或未知终止只读对账，不重发签名。

本Task只收口本地签名产物；完整恢复、正式身份/配置/8浏览器与自然首链继续全恢复Task，未通过不得报系统恢复完成。

实际入口校正：原output在仓库内被SIGNING_OUTPUT_INVALID拒绝，state/key均不存在，属于明确零效果失败。保留原输出边界，不放宽代码；通过独立临时目录接收无秘密receipt，成功后精确复制到Task证据路径。签名state仍为登记的独立目录。
