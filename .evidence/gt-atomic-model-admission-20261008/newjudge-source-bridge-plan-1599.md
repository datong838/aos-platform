# 新 Judge Source 原事实桥：1598 接续计划

当前 m1 2e330ca7，AOS-001598，原 Task/Lease 单写有效。上一波预算全局排序仅内部必要前缀，未证明 Source 联合入口。

## 已登记候选及依赖
1. 新 Judge 原事实桥：原申请、独立审批、Judge parent 与三预算桶、新鲜 xmin、Source 签名与 provider/quota 映射。已授权隔离实现；依赖联合顺序与完整案例合同，不安装正式库。
2. whole Manifest 新用途及 parent 类型：已由 gt-model-typed-proof-20261008 登记；依赖第一项原事实格式与父金额/token 绑定。先调查合同，不扩大 DTO 为执行权威。

## 本阶段文件与 RED
只在本 Task 证据目录写计划、冻结资料和缺失入口 RED：test_newjudge_source_bridge_entry_red.py / newjudge-source-bridge-red-r1.log / newjudge-source-bridge-investigation-1598.json。先验证独立编译器 occupation_judge_fact_statements 缺失；此 RED 只证明入口未实现，不证明权限或数据库行为。
下一实现文件 services/aos-api/aos_api/aip_physical_capacity_occupation_authority.py。新增独立常量、函数编译器与原权限入口，保持 occupation_eval_fact_statements 原 SQL 字节不变。新原事实必须读取原 aip_model_judge_budget_reservation、aip_model_eval_judge_request、原独立审批及完整两申请图；parent/三桶 xmin 同当前调用，request/hash/purpose/price/budget/currency/金额/限额/有效期全绑定，Source 原签名与 provider/quota 来源必须一致。不采用 caller 自报 preparation。

## 顺序及未证明事项
现有 require_current_approval 通过 graph reader 对旧申请 proposal 取 FOR SHARE；原 Model hold 对 proposal 取 FOR UPDATE。未来联合入口若同时升级共享锁须审计原 graph 全部 proposal，按统一键先持有需要的排他锁、等待后重新走原权威图。静态证据目前不能证明已发生死锁。不得在 Source/physical/bucket 顺序之外倒取费用锁，不新增重试掩盖顺序问题。

Source 新用途原桥的 DB RED/GREEN 需完整原生159、原C签名门、独立Source issuance同进程及资源门；现有 Source 已过期，不能续旧签名时窗，临时库余量有限，不能清库或再克隆。先编译器入口RED，后实现与专项数据库负门；不得宣称单测、编译器字符串或 old v1 Source 证明新用途全链。

## 验收与交付
验收新增用途的原审批、金额、三桶、新鲜caller/Source/完整case，以及 withdrawal/expiry/跨租户/跨caller/提前COMMIT/私有finalizer。当前研究和RED不关闭父Task，不改变 Goal active，不打开正式执行入口。不将缺失入口标为整体停工。

## 原生顺序调查回读
R2完整原测试+原方法并发组合1PASS53.60s；第二caller真实等待原Registry advisory(228,1)，first=blocker，双方pg_xact_status=aborted、Targethold零、无其他活跃client。该组合未复现proposal升级死锁，不因猜测改原锁。后续新Source联合入口必须保留原Registry前缀，不能绕过或全局取消；此证据不是Source物理account联合承诺。
