# Source 实际提交截止边界：后置步骤审计

Rules：231、原联合实施合同、单一 m1 写者；仅本证据目录及已保留实验库 READ ONLY，不改业务代码、安装扩展、重放反例或触碰正式库。

候选一：实际 COMMIT 截止门，依赖原已提交过期 Source 反例、完整结束通道及可信事务绑定；候选二：typed Model/Route 联合执行证明，依赖唯一 Intent、原预算与签名 Owner。选择候选一的独立前置审计，不以累计 386 项通过代替截止门。

具体文件：本目录 register.py、audit_boundary.py、upstream-xact.c、boundary-audit.json、boundary-contract.md、checkpoint.json。先官方登记 Task/Lease，冻结当前 HEAD、原反例与产品输入 hash，下载官方 REL_16_14 源码；机械核对 deferred/portal → PRE_COMMIT → 后续可等待步骤 → WAL/CLOG → 同步复制的实际顺序及 callback 注册顺序。针对完整累计中的一个真实签名 Source 保留库，以 SERIALIZABLE READ ONLY 核实例身份、durability、原 Source 及触发器定义、配置与临时接口缺席。不安装任何 callback，不执行旧 COMMIT。

验收：原反例与业务文件 hash 不变；原签名 Source/xid 仍可独立验证；源代码锚点顺序一致；读事务明确 READ ONLY；结果区分最终可回滚决策点、WAL 持久化、客户端确认，不把三者视为同一时间。若后置步骤仍可等待，则 PRE_COMMIT 本身不能满足严格完成截止，保留 RED 并明确下一协议候选及所需正式安装范围。无浏览器适用。
