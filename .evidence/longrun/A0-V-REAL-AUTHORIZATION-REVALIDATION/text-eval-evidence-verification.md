# 历史真实文本评测证据核验

2026-09-11，基线228b7433，Task A0V-TEXT-EVAL-EVIDENCE-20260911。

新增scripts/a0v_text_eval_evidence.py只读三个固定样本Journal，重建原exact_text请求，按序列化哈希严格比较整个identity（避免Python true==1），检查完成、模型/合同严格true、字段白名单、token整数与总量、输出上界、时区及24小时范围；超长/丢失/符号链接/重复JSON字段拒绝。输出原文件哈希、原观察时间和用量，不带prompt/expected/answer，不生成Gate。

测试先因模块未实现无法收集；实现后13通过；补true冒充版本1负例先失败，再修复为序列化哈希比较。最终新读取器14项与原健康/受限探针22项合计36通过；diffcheck通过。现有7警告/JDBC退出日志问题保留。

实际回读当前Provider/Network最新版本，与既有三记录一致；sourceHash c7852874e45f4a3a71120fbe79ec9e34b6b871b47ac9f59ef1ca30e07b9286dd。原观察时间2026-09-10T17:38:54.448609Z、17:38:55.206160Z、17:38:55.626557Z；本次0 Provider调用/0 DB写入，未把旧时间刷新。受限本地结果.aos-recovery-20260910/logs/verified-text-evidence-20260911.json。

限制：信任已授权本地执行器Journal，非远端签名；旧记录不保存回答正文，本工具不能独立重算回答，仅校验原执行器明确合同判定及绑定。来源不是当前健康；上一健康观察已于北京时间12:15:56到期。后续正式Dataset/Suite/Runner/Release必须标明verified prior probe，并限定开发模型授权窗口不越过证据最大年龄；新候选配置做独立当前治理核验，不能把历史Provider探针写成当时经过注册模型/路由运行。

下一波完成正式评测来源登记与模型/路由exact发布。尚未发布业务计划、模型路由或激活安装；首链/八场景仍未完成，不push，230 L0挂起。
