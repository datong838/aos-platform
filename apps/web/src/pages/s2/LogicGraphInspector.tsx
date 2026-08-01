import { useEffect, useState } from "react";

import type { LogicGraphNode } from "./logicCanvasGraph";

export type LogicInspectorDirtyReason = "node_label" | "node_config" | "entry_change";

export interface LogicGraphInspectorProps {
  selectedNode: LogicGraphNode | null;
  entryNodeIds: string[];
  disabled?: boolean;
  onNodeChange: (node: LogicGraphNode) => void;
  onEntryNodeIdsChange: (entryNodeIds: string[]) => void;
  onDirty: (reason: LogicInspectorDirtyReason) => void;
  onValidationError?: (message: string) => void;
}

type Drafts = Record<string, string>;

const STRING_CONFIG_KEYS = [
  "name",
  "expression",
  "property",
  "source",
  "prompt",
  "model",
  "tool",
  "action",
  "target",
  "decision",
] as const;

const HANDOFF_TARGETS = new Set(["risk_agent", "draft_inbox", "webhook"]);
const BRANCH_PATH_KEYS = new Set(["id", "label", "condition", "color", "default"]);
const ACTION_EDIT_KEYS = new Set(["object_id", "field", "value"]);

function prettyJson(value: unknown, fallback: unknown): string {
  try {
    return JSON.stringify(value ?? fallback, null, 2);
  } catch {
    return JSON.stringify(fallback, null, 2);
  }
}

function draftsFor(node: LogicGraphNode | null): Drafts {
  if (!node) return {};
  const drafts: Drafts = {
    label: node.label,
    schema: prettyJson(node.config.schema, {}),
    paths: prettyJson(node.config.paths, []),
    arguments: prettyJson(node.config.arguments, {}),
    edits: prettyJson(node.config.edits, []),
    request: prettyJson(node.config.request, {}),
  };
  STRING_CONFIG_KEYS.forEach((key) => {
    drafts[key] = typeof node.config[key] === "string" ? node.config[key] as string : "";
  });
  return drafts;
}

function parseJson(text: string, label: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`${label} JSON 格式无效：${detail}`);
  }
}

function parseSchema(text: string): Record<string, unknown> {
  const value = parseJson(text, "Input Schema");
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Input Schema 必须是 JSON 对象");
  }
  return value as Record<string, unknown>;
}

function parseJsonObject(text: string, label: string): Record<string, unknown> {
  const value = parseJson(text, label);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 必须是 JSON 对象`);
  }
  return value as Record<string, unknown>;
}

function parseActionEdits(text: string): Record<string, unknown>[] {
  const value = parseJson(text, "Action Edits");
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error("Action Edits 必须是非空 JSON 数组");
  }
  return value.map((candidate, index) => {
    const label = `Action edit #${index + 1}`;
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      throw new Error(`${label} 必须是对象`);
    }
    const edit = candidate as Record<string, unknown>;
    const unknownKeys = Object.keys(edit).filter((key) => !ACTION_EDIT_KEYS.has(key));
    if (unknownKeys.length > 0) {
      throw new Error(`${label} 包含未知字段：${unknownKeys.join(", ")}`);
    }
    if (typeof edit.object_id !== "string") {
      throw new Error(`${label} 的 object_id 必须是字符串`);
    }
    if (typeof edit.field !== "string") {
      throw new Error(`${label} 的 field 必须是字符串`);
    }
    const objectId = edit.object_id.trim();
    const field = edit.field.trim();
    if (!objectId || !field) {
      throw new Error(`${label} 的 object_id、field 均不能为空`);
    }
    if (!Object.prototype.hasOwnProperty.call(edit, "value")) {
      throw new Error(`${label} 必须包含 value`);
    }
    return { object_id: objectId, field, value: edit.value };
  });
}

function parseBranchPaths(text: string): Record<string, unknown>[] {
  const value = parseJson(text, "Branch Paths");
  if (!Array.isArray(value) || value.length === 0) {
    throw new Error("Branch Paths 必须是非空 JSON 数组");
  }
  const ids = new Set<string>();
  let defaultCount = 0;
  return value.map((candidate, index) => {
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) {
      throw new Error(`Branch path #${index + 1} 必须是对象`);
    }
    const path = candidate as Record<string, unknown>;
    const unknownKeys = Object.keys(path).filter((key) => !BRANCH_PATH_KEYS.has(key));
    if (unknownKeys.length > 0) {
      throw new Error(`Branch path #${index + 1} 包含未知字段：${unknownKeys.join(", ")}`);
    }
    const id = typeof path.id === "string" ? path.id.trim() : "";
    const label = typeof path.label === "string" ? path.label.trim() : "";
    const condition = typeof path.condition === "string" ? path.condition.trim() : "";
    if (!id || !label || !condition) {
      throw new Error(`Branch path #${index + 1} 的 id、label、condition 均不能为空`);
    }
    if (ids.has(id)) throw new Error(`Branch path ID 重复：${id}`);
    ids.add(id);
    if (path.default !== undefined && typeof path.default !== "boolean") {
      throw new Error(`Branch path ${id} 的 default 必须是 boolean`);
    }
    const isDefault = path.default === true;
    if (isDefault) defaultCount += 1;
    if (defaultCount > 1) throw new Error("Branch Paths 最多允许一个 default 路径");
    if (path.color !== undefined && (typeof path.color !== "string" || !path.color.trim())) {
      throw new Error(`Branch path ${id} 的 color 必须是非空字符串`);
    }
    return {
      id,
      label,
      condition,
      ...(path.color === undefined ? {} : { color: (path.color as string).trim() }),
      default: isDefault,
    };
  });
}

function TextEditor({
  label,
  draft,
  disabled,
  multiline = false,
  onDraftChange,
  onApply,
}: {
  label: string;
  draft: string;
  disabled: boolean;
  multiline?: boolean;
  onDraftChange: (value: string) => void;
  onApply: () => void;
}) {
  return (
    <div className="bp-logic-canvas-inspector-field">
      <label>
        <span>{label}</span>
        {multiline ? (
          <textarea
            aria-label={label}
            value={draft}
            rows={4}
            disabled={disabled}
            onChange={(event) => onDraftChange(event.target.value)}
          />
        ) : (
          <input
            aria-label={label}
            value={draft}
            disabled={disabled}
            onChange={(event) => onDraftChange(event.target.value)}
          />
        )}
      </label>
      <button type="button" className="btn" aria-label={`应用${label}`} disabled={disabled} onClick={onApply}>
        应用
      </button>
    </div>
  );
}

function JsonEditor({
  label,
  applyLabel,
  draft,
  disabled,
  rows,
  onDraftChange,
  onApply,
}: {
  label: string;
  applyLabel: string;
  draft: string;
  disabled: boolean;
  rows: number;
  onDraftChange: (value: string) => void;
  onApply: () => void;
}) {
  return (
    <div className="bp-logic-canvas-inspector-field is-stacked">
      <label>
        <span>{label}</span>
        <textarea
          aria-label={label}
          value={draft}
          rows={rows}
          disabled={disabled}
          spellCheck={false}
          onChange={(event) => onDraftChange(event.target.value)}
        />
      </label>
      <button type="button" className="btn" aria-label={`应用 ${applyLabel}`} disabled={disabled} onClick={onApply}>
        应用 {applyLabel}
      </button>
    </div>
  );
}

export function LogicGraphInspector({
  selectedNode,
  entryNodeIds,
  disabled = false,
  onNodeChange,
  onEntryNodeIdsChange,
  onDirty,
  onValidationError,
}: LogicGraphInspectorProps) {
  const configSignature = selectedNode ? prettyJson(selectedNode.config, {}) : "";
  const [drafts, setDrafts] = useState<Drafts>(() => draftsFor(selectedNode));
  const [validationError, setValidationError] = useState("");

  useEffect(() => {
    setDrafts(draftsFor(selectedNode));
    setValidationError("");
  }, [selectedNode?.id, selectedNode?.label, configSignature]);

  function updateDraft(key: string, value: string): void {
    setDrafts((previous) => ({ ...previous, [key]: value }));
    setValidationError("");
  }

  function failValidation(message: string): void {
    setValidationError(message);
    onValidationError?.(message);
  }

  function commitNode(next: LogicGraphNode, reason: LogicInspectorDirtyReason): void {
    if (!selectedNode || JSON.stringify(next) === JSON.stringify(selectedNode)) {
      setValidationError("");
      return;
    }
    onNodeChange(next);
    onDirty(reason);
    setValidationError("");
  }

  function commitLabel(): void {
    if (!selectedNode) return;
    const value = (drafts.label || "").trim();
    if (!value) {
      failValidation("Block 标签不能为空");
      return;
    }
    commitNode({ ...selectedNode, label: value }, "node_label");
  }

  function commitStringConfig(key: string, label: string): void {
    if (!selectedNode) return;
    const value = (drafts[key] || "").trim();
    if (!value) {
      failValidation(`${label} 不能为空`);
      return;
    }
    commitNode({
      ...selectedNode,
      config: { ...selectedNode.config, [key]: value },
    }, "node_config");
  }

  function commitOptionalStringConfig(key: string): void {
    if (!selectedNode) return;
    const value = (drafts[key] || "").trim();
    const config = { ...selectedNode.config };
    if (value) config[key] = value;
    else delete config[key];
    commitNode({ ...selectedNode, config }, "node_config");
  }

  function commitJsonConfig(
    key: string,
    parser: (text: string) => Record<string, unknown> | Record<string, unknown>[],
  ): void {
    if (!selectedNode) return;
    try {
      const value = parser(drafts[key] || "");
      commitNode({ ...selectedNode, config: { ...selectedNode.config, [key]: value } }, "node_config");
    } catch (error) {
      failValidation(error instanceof Error ? error.message : String(error));
    }
  }

  function commitSchema(): void {
    if (!selectedNode) return;
    try {
      const schema = parseSchema(drafts.schema || "");
      commitNode({ ...selectedNode, config: { ...selectedNode.config, schema } }, "node_config");
    } catch (error) {
      failValidation(error instanceof Error ? error.message : String(error));
    }
  }

  function commitPaths(): void {
    if (!selectedNode) return;
    try {
      const paths = parseBranchPaths(drafts.paths || "");
      commitNode({ ...selectedNode, config: { ...selectedNode.config, paths } }, "node_config");
    } catch (error) {
      failValidation(error instanceof Error ? error.message : String(error));
    }
  }

  function toggleEntry(): void {
    if (!selectedNode || disabled) return;
    const isEntry = entryNodeIds.includes(selectedNode.id);
    const next = isEntry
      ? entryNodeIds.filter((nodeId) => nodeId !== selectedNode.id)
      : [...new Set([...entryNodeIds, selectedNode.id])];
    onEntryNodeIdsChange(next);
    onDirty("entry_change");
    setValidationError("");
  }

  function updateHandoffTarget(value: string): void {
    if (!selectedNode) return;
    if (!HANDOFF_TARGETS.has(value)) {
      failValidation(`未知 Handoff 目标：${value}`);
      return;
    }
    commitNode({
      ...selectedNode,
      config: { ...selectedNode.config, handoff_to: value },
    }, "node_config");
  }

  if (!selectedNode) {
    return (
      <section className="bp-logic-canvas-inspector-panel" aria-label="Logic Block 属性">
        <h3>Block 属性</h3>
        <p className="bp-logic-canvas-inspector-empty">选择一个 Block 查看和编辑属性</p>
      </section>
    );
  }

  const isEntry = entryNodeIds.includes(selectedNode.id);
  const textEditor = (label: string, key: string, multiline = false) => (
    <TextEditor
      label={label}
      draft={drafts[key] || ""}
      disabled={disabled}
      multiline={multiline}
      onDraftChange={(value) => updateDraft(key, value)}
      onApply={() => commitStringConfig(key, label)}
    />
  );

  return (
    <section className="bp-logic-canvas-inspector-panel" aria-label="Logic Block 属性">
      <div className="bp-logic-canvas-inspector-heading">
        <div>
          <h3>Block 属性</h3>
          <code>{selectedNode.kind}</code>
        </div>
        <label className="bp-logic-canvas-inspector-entry">
          <input
            type="checkbox"
            aria-label="设为入口节点"
            checked={isEntry}
            disabled={disabled}
            onChange={toggleEntry}
          />
          入口节点
        </label>
      </div>

      <div className="bp-logic-canvas-inspector-field">
        <label>
          <span>标签</span>
          <input
            aria-label="Block 标签"
            value={drafts.label || ""}
            disabled={disabled}
            onChange={(event) => updateDraft("label", event.target.value)}
          />
        </label>
        <button type="button" className="btn" aria-label="应用标签" disabled={disabled} onClick={commitLabel}>
          应用
        </button>
      </div>

      {selectedNode.kind === "input" && (
        <div className="bp-logic-canvas-inspector-field is-stacked">
          <label>
            <span>Input Schema JSON</span>
            <textarea
              aria-label="Input Schema JSON"
              value={drafts.schema || ""}
              rows={8}
              disabled={disabled}
              spellCheck={false}
              onChange={(event) => updateDraft("schema", event.target.value)}
            />
          </label>
          <button type="button" className="btn" aria-label="应用 Input Schema" disabled={disabled} onClick={commitSchema}>
            应用 Schema
          </button>
        </div>
      )}

      {selectedNode.kind === "create_variable" && (
        <>
          {textEditor("变量名", "name")}
          {textEditor("变量表达式", "expression", true)}
        </>
      )}
      {selectedNode.kind === "get_property" && (
        <>
          {textEditor("Property", "property")}
          <TextEditor
            label="Source"
            draft={drafts.source || ""}
            disabled={disabled}
            onDraftChange={(value) => updateDraft("source", value)}
            onApply={() => commitOptionalStringConfig("source")}
          />
        </>
      )}
      {selectedNode.kind === "use_llm" && (
        <>
          {textEditor("Prompt", "prompt", true)}
          {textEditor("Model", "model")}
        </>
      )}
      {selectedNode.kind === "use_tool" && (
        <>
          {textEditor("Tool", "tool")}
          <JsonEditor
            label="Tool Arguments JSON"
            applyLabel="Tool Arguments"
            draft={drafts.arguments || ""}
            disabled={disabled}
            rows={6}
            onDraftChange={(value) => updateDraft("arguments", value)}
            onApply={() => commitJsonConfig("arguments", (text) => parseJsonObject(text, "Tool Arguments"))}
          />
        </>
      )}
      {selectedNode.kind === "transform" && textEditor("Expression", "expression", true)}
      {selectedNode.kind === "apply_action" && (
        <>
          {textEditor("Action", "action")}
          <JsonEditor
            label="Action Edits JSON"
            applyLabel="Action Edits"
            draft={drafts.edits || ""}
            disabled={disabled}
            rows={8}
            onDraftChange={(value) => updateDraft("edits", value)}
            onApply={() => commitJsonConfig("edits", parseActionEdits)}
          />
        </>
      )}
      {selectedNode.kind === "execute" && (
        <>
          {textEditor("Target", "target")}
          <JsonEditor
            label="Execute Request JSON"
            applyLabel="Execute Request"
            draft={drafts.request || ""}
            disabled={disabled}
            rows={6}
            onDraftChange={(value) => updateDraft("request", value)}
            onApply={() => commitJsonConfig("request", (text) => parseJsonObject(text, "Execute Request"))}
          />
        </>
      )}

      {selectedNode.kind === "branch" && (
        <div className="bp-logic-canvas-inspector-field is-stacked">
          <label>
            <span>Branch Paths JSON</span>
            <textarea
              aria-label="Branch Paths JSON"
              value={drafts.paths || ""}
              rows={12}
              disabled={disabled}
              spellCheck={false}
              onChange={(event) => updateDraft("paths", event.target.value)}
            />
          </label>
          <button type="button" className="btn" aria-label="应用 Branch Paths" disabled={disabled} onClick={commitPaths}>
            应用 Paths
          </button>
        </div>
      )}

      {selectedNode.kind === "handoff" && (
        <>
          {textEditor("Decision", "decision", true)}
          <label className="bp-logic-canvas-inspector-select">
            <span>Handoff To</span>
            <select
              aria-label="Handoff To"
              value={typeof selectedNode.config.handoff_to === "string" ? selectedNode.config.handoff_to : "draft_inbox"}
              disabled={disabled}
              onChange={(event) => updateHandoffTarget(event.target.value)}
            >
              <option value="risk_agent">risk_agent</option>
              <option value="draft_inbox">draft_inbox</option>
              <option value="webhook">webhook</option>
            </select>
          </label>
        </>
      )}

      {validationError && (
        <p className="bp-logic-canvas-inspector-error" role="alert">{validationError}</p>
      )}
    </section>
  );
}
