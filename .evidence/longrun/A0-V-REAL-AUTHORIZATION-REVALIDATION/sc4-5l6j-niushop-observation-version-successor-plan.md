# SC4-5l6j Niushop P02 观测版本后继包与 E 代安装方案

日期：2026-09-15  
基线：`f52fbb42`  
owner：`m1`；不 push；230 L0 挂起。  
前置事实：`scr-f22003e66e544ebe` 已知 stopped/failed，真实 65 行命令已保存但与旧 Receipt 撞键；64 行相同，商品 32 的库存/销量变化而源修改时间不变。

## 目标

生成只修复 P02 时间语义的 `platform.ecommerce.niushop@1.23.0`，完成构建、资格检查、签名注册和 D→E 正式重装。E 成为唯一 current active/ready/enabled/unfenced 代次后，重新建立 E 的 P02 SourceSelection、RuntimeControl 与 ScheduleBinding，再允许一次新鲜只读批次。原 D 失败 Run 和所有旧 Receipt 永久保留。

## Rules

1. 先候选、测试、构建、资格、签名，后迁移安装；签名目录和已发布 1.22 不可修改。
2. 1.23 以仓库候选 1.22 冻结树 `sha256:f0ef69161dbae032fb29da036fa3cf9e9ef6dca1224027d9225d25df49eb8088` 为源；只允许修改 `bundle.yaml`、`content/mappings/p02-product.yaml`、`evidence/bundle-evals.json`。
3. P02 改用既有 `aos.snapshot-materialization/v3`，固定 `time_basis=observation`；显式 tombstone 与 status 规则保持原值。v2 通用实现、权威 Store、同版本冲突、checkpoint、Receipt 和投影语义均不修改。
4. 新静态 eval 必须编译 1.23 P02，证明观测时间进入版本与审计属性、重复使用同一观测时间确定、不同观测时间形成不同版本、非法声明失败关闭；不把静态测试冒充真实租户成功。
5. 构建 profile 和签名 successor 只把 Niushop 版本从 1.22 指向 1.23，其余 core 1.3、growth 1.8、operations-base 1.2 的内容 hash 必须保持。
6. D→E：先冻结 D 当前状态，优雅停止旧 Host并确认资源 released；由新包根启动新 Host，正式 settle D 为 disabled；E 以前述 D exact head 创建，依次 prepare/verify/stage/configure/enable。不得手工启动容器或改控制表。
7. E 的 P02 preflight 和业务控制器必须从 E create Receipt 与 1.23 签名资产导出 exact ref；历史 D refs 一律拒绝。
8. 正租户固定 `org-org/dev-project`，canary `dev-org/dev-project` 零写；源库只读；无发布、触达、投流、价格、库存或履约写。
9. 任一步结果未知先读 Receipt；同一阶段失败两次停止该写动作并保留证据，不换 key 猜测重发。

## 代码和资产范围

新增：

- `scripts/prepare_niushop_product_observation_candidate.py`
- `services/aos-api/tests/extension_runtime/test_niushop_product_observation_candidate.py`
- `bundles/candidates/ecommerce/platform.ecommerce.niushop/1.23.0/**`（由脚本一次生成，不覆盖）
- 本方案与后续验证文档。

修改：

- `scripts/build_ecommerce_current_candidates.py` 与对应测试：current profile 指向 1.23。
- `scripts/a0v_ecommerce_current_signed_successor.py` 与对应测试：新 signed root/版本/count。
- `scripts/a0v_ecommerce_current_reinstall.py` 与对应测试：增加 D settlement、E create/prepare/verify/stage/configure/enable，E 前驱固定 D。
- `scripts/a0v_p02_current_preflight.py` 与对应测试：current create 改为 E，Niushop 1.23。
- `scripts/a0v_qyh_current_product_event_first_chain.py` 与对应测试：新的 E 私有状态目录和新幂等控制身份，禁止复用 D 的 exhausted/failed intent。

## preHash

- 1.22 候选树：`sha256:f0ef69161dbae032fb29da036fa3cf9e9ef6dca1224027d9225d25df49eb8088`
- `scripts/build_ecommerce_current_candidates.py`：`d50c0b430c69ff772ec7aeaac6a77023387e3adb`
- `scripts/a0v_ecommerce_current_signed_successor.py`：`dd65149be5f7c1ec25a82ec9969b7ec20192a158`
- `scripts/a0v_ecommerce_current_reinstall.py`：`94f1dc6c5316b01df826a1cd3e2b2fda404e8713`
- `scripts/a0v_p02_current_preflight.py`：`25e7a9de680dabc943135910f56d41f7d0786ea4`
- 新候选脚本、测试、1.23 树：`NEW`。

## 六步退出条件

1. 1.22 树、v3 正式实现、构建/签名/重装入口和 D 当前事实盘点完成。
2. 本方案、范围、preHash、停止条件提交。
3. 1.23 候选生成；唯一允许的三类文件变化与静态 eval 全绿。
4. 四包构建、资格与签名注册完成；旧签名根不变，租户安装数不变，canary 为零。
5. D 安全释放并正式 disabled；E 完成全生命周期且三个 OCI 与三 Worker 健康。
6. E P02 current preflight 与新控制 refs 就绪；进入新鲜批次及 ProductEvent/Case 自然链复验。

## 完成边界

本波只关闭真实 P02 的源版本合同缺口并把修复安装为 current。只有后续 E 批次 succeeded、Dataset exact 完成且 Worker 自然生成 Occurrence/Analysis，才关闭上一波第 4/6 与第 5/6；更后面的 exact 评审、内容任务、能力、产物、人工评审续跑、总控复盘、Wiki 与八工作台仍继续逐波验证。
