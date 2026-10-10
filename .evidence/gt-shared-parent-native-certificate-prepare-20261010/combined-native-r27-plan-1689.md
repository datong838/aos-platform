# R27 诊断开销隔离复验
Rules：231/原Task10 E，m1唯一writer、不延期原批准/签名/Source。R26 terminal129.71s，原Judge期限门在occupation replay拒绝，独立READ ONLY风险metadata0/Root1/12源hash相同；R24/25总时102.01/127.81s，尚不能证明deadline根因仅诊断。
候选一：去除实验全进程sys.settrace的额外诊断开销并fresh复验；候选二：完整目录/事件闭包只读核对。先一，再二。精确本Task/native-r27/run-native-r27.py，helper保持R26hash语义不变、Task3独立label。只去额外全进程逐调用跟踪，不删任何负矩阵/幂等/原currentness/期限验证，真实pytest异常仍入日志；exceptiondiagnostics明确未开启，不假装有细粒度跟踪证据。新DB/110s批准/Root/证书，新调用不重放旧请求或未知效果。若仍期限拒绝，保留真实RED并研究原合同范围内性能，不扩大窗口或假成功。
