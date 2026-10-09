# 专属读取门真实时间跨认证到期

Rules：231固定八步、当前原件权威、单writer；当前Task/Lease不重叠，基线ba6b40a1 / AOS-001676。候选一补读取后真实认证到期（本波）；候选二原风险与identity同caller只读桥（依本波与原issuer窄权限设计）；正式bootstrap/Transport不借测试授权。

改动仅 services/aos-api/tests/aip/test_shared_parent_description_origin_reader_pg.py；产品新reader先保持不变。原描述生产者已在同事务保留Source/审批行锁，不能编造rival已先取得那些行的排他锁，再称读取者真实等待。采用明确标记的测试同步屏障：读取函数的 typed description 解析完成、原生SQL已返回原件之后才等待；实际调用原Pydantic解析，保留原返回值、实际Owner/Source/SQL逻辑，不mockclock、不伪造认证或读结果。该证据是原件读取后的真实时间等待，不宣称PG行锁阻塞。

由现有实验HTTPS/JWKS signer新签发同subject、同tenant、同SourceRef的8秒JWT；先真实验签取得认证exp。读取前仍有效，SQL原件取得后用原数据库clock记录xidpid/全文hash，在同步屏障按真实墙钟跨过exp，再由真实Owner/Source后置校验拒绝。保留实际异常链类别/SQLSTATE而非只pytest.raises；校验前后同xidpid、等待不少于实际deadline、返回值为None未冒充成功。原长认证command和批准/Source原件不变，负门回滚保存点，随后原长认证仍能读取且完整节点继续。

先保留R2时测试文件精确源码/hash；新native R3 fresh Source/批准/认证，原100秒批准及300秒新认证实验范围沿用，不延R1/R2过期原件。追加相邻334纯验、原完整两case四leg/debit/input/Intent/guard竞争，完整节点结束再独立只读确认ABORTED、四风险表0、函数体/ACL/所有冻结hash。若失败先只读对账，不能将屏障子步当完整节点通过。

此波不能闭合所有SourceTTL/审批撤回竞争；分别记实。身份同caller/root谱系/finaljoint/真实token/WAL-ACK/正式经营首链继续待验，无Task Delivery。无UI变化，浏览器不适用。

R3 专属认证到期负门通过，真实异常链ExpiredSignatureError且SQL原件已解析、前后xidpid同一；整个节点在随后原联合复核因JUDGE_CURRENT_APPROVAL_REQUIRED失败。独立只读原风险ABORTED/四表0，失败不计绿。R4为新Source/新原申请/新批准原件，独立批准110秒以涵盖本波真实等待，仍在原请求2分钟/签名Rule3分钟内；旧100秒原件、产品审批/请求/Source时限不变、不扩过期窗口，不mockclock。新增10秒仅新实验批准，不改旧fixture文件或产品检查。

R4 110秒新批准仍在后续联合复核到期，专属负门通过、整轮FAIL。原审批/Proposal结束21:59:21.277134、原Request结束21:59:30.736656，进一步延长不能作为产品修复。复审测试恢复判据：负门前已真实完整原件正向多次；负门后要证明原长认证仍有效，改为实际Source消费并与屏障前真实Source返回值相等，不重复整套Owner/准备态读取。完整节点后续Owner/原描述反例/debit/input/Intent/guard验证全部保留。此调整仅测试恢复范围，不削弱到期反例、原件读取、后置拒绝或产品门。R5 fresh独立110秒批准/300秒认证，保留R3/R4精确源码和失败证据。

R5在保护旧摘要预检失败，未调用pytest/未创建新DB；误替换历史result-r4文件名。R6仅修独立运行器的旧原件路径，准确保留历史r4；新attempt/result/output仍独立r6，产品与测试逻辑不变。

R6同样停在路径预检（复制处理误改了历史suffix），未进入native。R7改用精确带引号的新attempt/result名称替换，启动前逐个断言所有保护原件存在；helper采用已有完整四份源码，不尝试复制运行时生成文件。

R7完成独立迁移和Source准备后，缺少隔离目录内两份helper而失败10.62秒，未到原风险读取；保留result与DB待只读核查。R8启动前精确克隆全部六helper，并逐项存在/hash校验；不重放R7数据库，另建fresh实验。
