import { type ChangeEvent } from "react";

export type BpCodeLanguage = "json" | "yaml" | "sql" | "text";

export function BpCodeEditor({
  value,
  onChange,
  language = "text",
  readOnly = false,
  minHeight = 120,
  errorMessage,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  language?: BpCodeLanguage;
  readOnly?: boolean;
  minHeight?: number;
  errorMessage?: string;
  ariaLabel?: string;
}) {
  return (
    <div className="bp-code-editor">
      <textarea
        className="bp-code-editor-textarea"
        value={value}
        readOnly={readOnly}
        spellCheck={false}
        wrap="off"
        aria-label={ariaLabel ?? `${language} 编辑器`}
        style={{ minHeight }}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
      {errorMessage ? <div className="bp-code-editor-error" role="alert">{errorMessage}</div> : null}
    </div>
  );
}
