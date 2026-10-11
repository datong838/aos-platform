# 恢复候选四包实际隔离构建与资格验证

基线m1 4e92beaca/AOS-001839，使用新独立profile，原builder不修改。目标四包 core1.4.3/platform1.23.0/Growth1.13.0/operations1.2.0；实际build输出 /Users/ddt/work/projects/ai_agent/aos-recovery/.aos-qyh-core143-build-20261011-r1，原CLI --build --retain-artifacts、context colima-aos-extension、测试只读registry loopback18442。构建 --network=none --pull=false，原镜像/卷保留，不操作真实Registry或部署服务。已有目标禁止覆盖，端口占用原门拒绝。

先完整build receipt、exact镜像/内容hash和source tree核对，然后原 --qualify-output --build-receipt 流程：新临时测试Ed25519身份、原解析/ReleasePolicy/resolver/schema门、隔离OCI registration/有限session、七类篡改拒绝。qualification不带retain-artifacts，原finally清除本次临时签名，不借用正式身份。这些无业务副作用测试不替代正式Host/运行授权。

保留intent与进程handle，失败不盲重放；只读检查实际输出/容器/receipt后修复或登记。完成结果与失败均如实记录；正式库/配置/安装/正式签名/页面仍待独立门，不以资格GREEN宣布栖月汇可用。
