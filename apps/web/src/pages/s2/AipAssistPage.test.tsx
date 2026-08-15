import { describe, expect, it } from "vitest";
import { subjectFromSearch } from "./AipAssistPage";

function params(): URLSearchParams {
  return new URLSearchParams({
    taskId: "task-1", taskRevision: "1", taskAuthority: "aip-task",
    taskRunId: "run-1", taskRunRevision: "2", taskRunAuthority: "aip-task-run",
    agentRunId: "agent-run-1", agentRunRevision: "3", agentRunAuthority: "aip-agent-run",
    cutoffAt: "2026-08-16T00:00:00Z",
  });
}

describe("AipAssistPage exact subject", () => {
  it("accepts only a complete exact upstream subject", () => {
    expect(subjectFromSearch(params())).toEqual(expect.objectContaining({ taskRef: expect.objectContaining({ resourceType: "Task", revision: "1" }), taskRunRef: expect.objectContaining({ resourceType: "TaskRun", revision: "2" }), agentRunRef: expect.objectContaining({ resourceType: "AgentRun", revision: "3" }) }));
  });
  it("does not invent a default AgentRun", () => { const value = params(); value.delete("agentRunAuthority"); expect(subjectFromSearch(value)).toBeNull(); });
});
