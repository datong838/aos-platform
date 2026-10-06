# S17完整四类原文与真实原生Ed25519组合调查

基线AOS-001402 / m1@3d535f1d。231/sql-approval-equivalence S17要求完整原文typed与真实crypto同时成立。候选一：四完整profile与原C Ed25519函数同事务组合实际验收；候选二：正式root/permit登记及签发COMMIT，需独立152/时间合同。先第一项只扩测试，无生产实现改动，不制造故意失败或假RED。

文件 services/aos-api/tests/aip/test_provider_capacity_publication_pg.py 和本目录，现publication Task/Lease。policy/attestation/permit/bootstrap均完整原模型生成canonical原文；在固定network-none r4隔离库同BEGIN中调用真实aos_ed25519.verify和原read对应profile。合法原始bytes先真验签再返回精确解析JSON，保留rawSHA。修改原文但保留旧signature、改signature、换public key均false；duplicate/schema/purpose故障独立重新真实签名（crypto true）后完整profile仍拒绝，不能以签名正确跳过文档门。各单故障对照原parse_signed_capacity_body，不使用mock verifier。

本调查验证必要前提的组合，测试调用者仍提供未受信任公钥，绝不证明正式root绑定、授权publisher/key/root currentness、bootstrap映射、签发/COMMIT或安装。BEGIN内函数回滚，无持续schema/DDL/role/真库或网络调用。专项与publication/Source合同相邻，证据hash/风险/精确提交及AOS/Prime同步，原Task不Delivery。

首轮4 failed/24 passed/9.16s：正向均因测试误调用密码学隔离库无public.digest失败，不是密码学失败。只改测试为pg_catalog.sha256，保持同原文hash与完整组合，不安装扩展；旧日志保留。
