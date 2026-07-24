#!/usr/bin/env python3
"""更新 220w 差距分析文档 — 同步已完成项 + 新增缺口"""
import re, sys, time

FILE = "/Users/ddt/work/projects/ai_agent/docs/palantier/20_tech/220w-与目标系统差距对照分析.md"

# 备份
import shutil
backup = FILE + ".bak." + str(int(time.time()))
shutil.copy2(FILE, backup)
print(f"备份: {backup}")

with open(FILE, "r", encoding="utf-8") as f:
    lines = f.readlines()

changes = []

# === 1. §6.1 k-LLM 路由表 (行 3104-3117) ===
# 用行号定位 + 正则替换状态标记
for i in range(len(lines)):
    line = lines[i]
    
    # 场景化路由 🔴→✅ (行 3108 附近)
    if "**场景化路由**" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无按任务类型选模；无块级选模", 
            "SmartRouter 5 维评分(#71) + ScenarioRouter 块级>场景>默认三级回落(#72)")
        changes.append(f"行 {i+1}: 场景化路由 🔴→✅")
    
    # 热切换与熔断 — 替换整行（emoji 可能损坏）
    if "**热切换与熔断**" in line:
        lines[i] = "| **热切换与熔断** | ✅ | FailoverEngine 3 态状态机 + cooldown + 演练(#73)\n"
        changes.append(f"行 {i+1}: 热切换与熔断 →✅")
    
    # 数据出境策略 🔴→✅
    if "**数据出境策略**" in line and "🔴" in line:
        lines[i] = "| **数据出境策略** | ✅ | EgressPolicyEngine 敏感标记+脱敏+审计抽检(#74)\n"
        changes.append(f"行 {i+1}: 数据出境策略 🔴→✅")
    
    # 自定义 LLM 注册 🔴→✅
    if "**自定义 LLM 注册**" in line and "🔴" in line:
        lines[i] = "| **自定义 LLM 注册** | ✅ | CustomLLMRegistry 三形态(#75)\n"
        changes.append(f"行 {i+1}: 自定义 LLM 注册 🔴→✅")
    
    # 模型路由策略页 🔴→✅
    if "**模型路由策略页**" in line and "🔴" in line:
        lines[i] = "| **模型路由策略页** | ✅ | aip-model-router.html 全局路由策略表\n"
        changes.append(f"行 {i+1}: 模型路由策略页 🔴→✅")

    # 差距结论行
    if "模型接入广度足够；但 k-LLM 核心能力" in line:
        lines[i] = "**差距结论**：模型接入广度足够；k-LLM 核心能力（场景化路由/熔断/数据出境/自定义注册）已全部完成(#71-75)。待完善：Modeling Objectives 评估流程、配额计费。\n"
        changes.append(f"行 {i+1}: 差距结论更新")

# === 2. §6.2 Logic 编排表 (行 3146-3162) ===
for i in range(len(lines)):
    line = lines[i]
    
    if "**三栏 UI**" in line and "🔴" in line and "仅占位" in line:
        lines[i] = "| **三栏 UI** | ✅ | LogicCanvasPage 三栏+拖拽+CoT 调试(#199 W2-C)\n"
        changes.append(f"行 {i+1}: 三栏 UI 🔴→✅")
    
    if "**Logic Block**" in line and "🔴" in line and "无任何块" in line:
        lines[i] = "| **Logic Block** | ✅ | 8 Block 类型(Input/Variable/GetProperty/UseLLM/Transform/ApplyAction/Conditionals/Execute)(#199)\n"
        changes.append(f"行 {i+1}: Logic Block 🔴→✅")
    
    if "**Use LLM + Tools**" in line and "🔴" in line:
        lines[i] = "| **Use LLM + Tools** | ✅ | 工具调用框架(#18 增强版 W2-B)\n"
        changes.append(f"行 {i+1}: Use LLM + Tools 🔴→✅")
    
    if "**Apply Action Block**" in line and "🔴" in line:
        lines[i] = "| **Apply Action Block** | ✅ | 确定性调用 Action(#199)\n"
        changes.append(f"行 {i+1}: Apply Action Block 🔴→✅")
    
    if "**工具集注册**" in line and "🔴" in line and "Query/Function" in line:
        lines[i] = "| **工具集注册** | ✅ | Capability 深度集成(#18 增强版 W2-B)\n"
        changes.append(f"行 {i+1}: 工具集注册 🔴→✅")
    
    if "**Ontology 写回四步**" in line and "🔴" in line:
        lines[i] = "| **Ontology 写回四步** | ✅ | WritebackLayer+Workshop 绑定(#19 增强版 W2-F)\n"
        changes.append(f"行 {i+1}: Ontology 写回四步 🔴→✅")
    
    if "**Edits 合并策略**" in line and "🔴" in line:
        lines[i] = "| **Edits 合并策略** | ✅ | field_level/last_write_wins/manual_arbitration(#76 W2-H)\n"
        changes.append(f"行 {i+1}: Edits 合并策略 🔴→✅")
    
    if "**Prompt 工程**" in line and "🔴" in line:
        lines[i] = "| **Prompt 工程** | ✅ | 变量注入/Few-shot/版本管理(#77 W2-U)\n"
        changes.append(f"行 {i+1}: Prompt 工程 🔴→✅")
    
    if "**调试器**" in line and "🔴" in line and "无 CoT" in line:
        lines[i] = "| **调试器** | ✅ | DebugSession+CoT+提议预览(#78 W2-V)\n"
        changes.append(f"行 {i+1}: 调试器 🔴→✅")
    
    if "**运行面板**" in line and "🔴" in line:
        lines[i] = "| **运行面板** | ✅ | run_to_completion+step_forward/backward(#78)\n"
        changes.append(f"行 {i+1}: 运行面板 🔴→✅")
    
    if "**Automate 集成**" in line and "🔴" in line and "无条件触发" in line:
        lines[i] = "| **Automate 集成** | ✅ | AutomateEngine 5 种 event_type+条件树+cooldown(#79 W2-V)\n"
        changes.append(f"行 {i+1}: Automate 集成 🔴→✅")

    # §6.2 差距结论
    if "Logic 编排为 AIP 最大缺口，完全从零开始" in line:
        lines[i] = "**差距结论**：Logic 编排核心能力已全部完成(#18/#19/#76-79/#199)。三栏 UI、8 种 Block 类型、工具集、调试器、写回路径、Automate 集成均已交付。待完善：Agent 六工具(#81-87)、L4 熔断/模型预热(#82-83)。\n"
        changes.append(f"行 {i+1}: §6.2 差距结论更新")

# === 3. §6.7 AIP Logic 对照表 (行 3312-3319) ===
for i in range(len(lines)):
    line = lines[i]
    
    if "**Logic Block 编辑器**" in line and "🔴" in line and "前端 mock" in line:
        lines[i] = line.replace("🔴", "✅").replace("前端 mock 4 类节点；无完整 Block 类型（Input/CreateVariable/GetProperty/UseLLM/Transform/ApplyAction）", 
            "8 Block 类型 + 拖拽 + CoT 调试(#199 W2-C)")
        changes.append(f"行 {i+1}: §6.7 Logic Block 编辑器 🔴→✅")
    
    if "**三栏 UI**" in line and "🔴" in line and "无左块链" in line:
        lines[i] = line.replace("🔴", "✅").replace("无左块链/中调试器/右运行面板三栏布局", 
            "LogicCanvasPage 三栏(#199)")
        changes.append(f"行 {i+1}: §6.7 三栏 UI 🔴→✅")
    
    if "**Ontology 写回四步**" in line and "🔴" in line and "无 UseLLM" in line:
        lines[i] = line.replace("🔴", "✅").replace("无 UseLLM→发布→Action→Workshop 端到端流程", 
            "WritebackLayer workshop_module 绑定(#19 W2-F)")
        changes.append(f"行 {i+1}: §6.7 Ontology 写回四步 🔴→✅")
    
    if "**Logic 执行引擎**" in line and "🔴" in line and "无实际运行" in line:
        lines[i] = line.replace("🔴", "✅").replace("无实际运行；仅 dryRun mock", 
            "LangGraph 运行时(#17 W2-F)")
        changes.append(f"行 {i+1}: §6.7 Logic 执行引擎 🔴→✅")
    
    if "**Automate 集成**" in line and "🔴" in line and "无自动化触发" in line:
        lines[i] = line.replace("🔴", "✅").replace("无自动化触发/条件编排", 
            "AutomateEngine 5 种 event_type(#79 W2-V)")
        changes.append(f"行 {i+1}: §6.7 Automate 集成 🔴→✅")

# === 4. §5.3.1.4 副作用表 (行 2953-2962) ===
for i in range(len(lines)):
    line = lines[i]
    
    if "通知规则" in line and "🔴" in line and "无通知配置" in line:
        lines[i] = line.replace("🔴", "✅").replace("无通知配置；无静态收件人/参数收件人/对象属性收件人/函数收件人",
            "4 来源收件人(static/parameter/object_property/function)(#63 W2-Q)")
        changes.append(f"行 {i+1}: §5.3.1.4 通知规则 🔴→✅")
    
    if "通知内容模板" in line and "🔴" in line and "无模板内容" in line:
        lines[i] = line.replace("🔴", "✅").replace("无模板内容配置；无主题/正文/链接/高级 HTML 邮件配置",
            "{{var}} 模板渲染 subject/body(#63)")
        changes.append(f"行 {i+1}: §5.3.1.4 通知内容模板 🔴→✅")
    
    if "Webhook 规则" in line and "🔴" in line and "无 Webhook 配置" in line:
        lines[i] = line.replace("🔴", "✅").replace("无 Webhook 配置；无数据输出/副作用两种模式",
            "data_output/side_effect 双模式(#64 W2-R)")
        changes.append(f"行 {i+1}: §5.3.1.4 Webhook 规则 🔴→✅")
    
    if "Webhook 数据输出模式" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无编辑前执行/事务性/失败阻断后续规则",
            "编辑前执行/事务性/失败阻断(#64)")
        changes.append(f"行 {i+1}: §5.3.1.4 Webhook 数据输出 🔴→✅")
    
    if "Webhook 副作用模式" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无编辑后执行/尽力而为/多 Webhook 并行",
            "编辑后执行/尽力而为/多 Webhook(#64)")
        changes.append(f"行 {i+1}: §5.3.1.4 Webhook 副作用模式 🔴→✅")
    
    if "Webhook 输入参数" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无操作参数映射/函数返回输入的配置",
            "input_mapping + {{var}} 模板(#64)")
        changes.append(f"行 {i+1}: §5.3.1.4 Webhook 输入参数 🔴→✅")
    
    if "Webhook 输出参数" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无数据输出 Webhook 的输出参数在后续规则中使用",
            "output_mapping + dot-path 响应提取(#64)")
        changes.append(f"行 {i+1}: §5.3.1.4 Webhook 输出参数 🔴→✅")

# === 5. §11 差距汇总矩阵 — 同步已完成项 ===
for i in range(len(lines)):
    line = lines[i]
    
    # k-LLM 智能路由
    if "k-LLM 智能路由" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#71)")
        changes.append(f"行 {i+1}: 矩阵 k-LLM 智能路由 🔴→✅")
    
    # k-LLM 场景化路由
    if "k-LLM 场景化路由" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#72)")
        changes.append(f"行 {i+1}: 矩阵 k-LLM 场景化路由 🔴→✅")
    
    # k-LLM 熔断/热切换
    if "k-LLM 熔断" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#73)")
        changes.append(f"行 {i+1}: 矩阵 k-LLM 熔断 🔴→✅")
    
    # 数据出境策略
    if "数据出境策略" in line and "🔴" in line and "敏感标记" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#74)")
        changes.append(f"行 {i+1}: 矩阵 数据出境策略 🔴→✅")
    
    # 自定义 LLM 注册
    if "自定义 LLM 注册" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#75)")
        changes.append(f"行 {i+1}: 矩阵 自定义 LLM 注册 🔴→✅")
    
    # Logic Block 全量
    if "Logic Block 全量" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#199)")
        changes.append(f"行 {i+1}: 矩阵 Logic Block 全量 🔴→✅")
    
    # Logic 三栏 UI
    if "Logic 三栏 UI" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#199)")
        changes.append(f"行 {i+1}: 矩阵 Logic 三栏 UI 🔴→✅")
    
    # 工具集注册
    if "工具集注册" in line and "🔴" in line and "Query/Function/Action" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#18)")
        changes.append(f"行 {i+1}: 矩阵 工具集注册 🔴→✅")
    
    # Ontology 写回四步
    if "Ontology 写回四步" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#19)")
        changes.append(f"行 {i+1}: 矩阵 Ontology 写回四步 🔴→✅")
    
    # Edits 合并策略
    if "Edits 合并策略" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#76)")
        changes.append(f"行 {i+1}: 矩阵 Edits 合并策略 🔴→✅")
    
    # Prompt 工程
    if "Prompt 工程" in line and "🔴" in line and "矩阵" not in line:
        # 矩阵里的
        if "变量注入" in line:
            lines[i] = line.replace("🔴", "✅").replace("无", "完成(#77)")
            changes.append(f"行 {i+1}: 矩阵 Prompt 工程 🔴→✅")
    
    # 调试器
    if "调试器" in line and "🔴" in line and "CoT" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#78)")
        changes.append(f"行 {i+1}: 矩阵 调试器 🔴→✅")
    
    # Automate 集成
    if "Automate 集成" in line and "🔴" in line and "条件触发" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#79)")
        changes.append(f"行 {i+1}: 矩阵 Automate 集成 🔴→✅")
    
    # AIP Logic 无代码编辑器
    if "AIP Logic 无代码编辑器" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("mock UI", "完成(#199)")
        changes.append(f"行 {i+1}: 矩阵 AIP Logic 编辑器 🔴→✅")
    
    # Action 事务回滚
    if "Action 事务回滚" in line and "🔴" in line:
        lines[i] = line.replace("🔴", "✅").replace("无", "完成(#70)")
        changes.append(f"行 {i+1}: 矩阵 Action 事务回滚 🔴→✅")

# === 6. 新增缺口行到 §11 矩阵末尾（在 §12 标题之前）===
# 找到 §12 标题行
section12_idx = None
for i in range(len(lines)):
    if "## 12. W1 分支建议优先项" in lines[i]:
        section12_idx = i
        break

if section12_idx:
    new_rows = [
        "\n",
        "| **G-ACT-02 Data Connection 链式 Webhook** | 无 | Call 1→Call 2 参数引用/Saga 补偿 | 🔴 | 中 |\n",
        "| **G-SEC-01 Ontology 层 MAC/DAC** | 基础 RBAC | 强制访问控制标签/行列级自主权限 | 🔴 | 中 |\n",
        "| **G-AIP-04 k-LLM Logic 内编排模式** | ✅ 底层已就绪 | Conditionals+多 Use LLM Block 编排模式(设计文档) | 🟡 | 低 |\n",
    ]
    # 在 §12 前的 `---` 分隔线前插入
    # 找分隔线
    insert_idx = section12_idx
    while insert_idx > 0 and lines[insert_idx - 1].strip() != "---":
        insert_idx -= 1
    
    for j, row in enumerate(new_rows):
        lines.insert(insert_idx + j, row)
    changes.append(f"在行 {insert_idx+1} 前新增 3 行缺口(G-ACT-02/G-SEC-01/G-AIP-04)")

# 写回
with open(FILE, "w", encoding="utf-8") as f:
    f.writelines(lines)

print(f"\n共 {len(changes)} 处修改:")
for c in changes:
    print(f"  ✓ {c}")
