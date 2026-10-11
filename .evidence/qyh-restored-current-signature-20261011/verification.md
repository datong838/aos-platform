# 当前四包本地签名验收

真实原build/qualification校验后生成独立Ed25519本地签名，core1.4.3/platform1.23.0/Growth1.13.0/operations1.2.0。首次仓库内receipt路径被原SIGNING_OUTPUT_INVALID拒绝，证明state/key不存在；保留原保护，改用临时无秘密receipt并精确复制Task证据。第二次exit0/SIGNED_TREE_GREEN，签名state在登记目录，0700/privatekey未输出。

独立进程重新加载4包/TrustRoot/ReleasePolicy并验证树hash及4个签名，原buildTreeHash相同且无持久签名。现有签名入口及候选、恢复接入相邻22项通过。无需浏览器：只生成本地静态候选，未切换当前Web/API。

RegistryPublish/installationMutation/Provider/externalPublication全0。本Task仅证明当前候选签名产物可用；不宣称正式Root/Owner/配置/自然首链或全系统恢复。
