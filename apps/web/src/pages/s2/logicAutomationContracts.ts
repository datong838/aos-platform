export type LogicAutomationTrigger = "manual" | "cron" | "event";
export type LogicAutomationStatus = "active" | "paused";

export interface LogicAutomationPolicy {
  automation_id: string;
  graph_id: string;
  publication_id: string;
  graph_revision: number;
  graph_hash: string;
  name: string;
  trigger_type: LogicAutomationTrigger;
  schedule: string;
  status: LogicAutomationStatus;
  revision: number;
  actor: string;
  created_at: string;
  updated_at: string;
}

export interface LogicAutomationRun {
  run_id: string;
  automation_id: string;
  policy_revision: number;
  trigger: LogicAutomationTrigger;
  task_id: string;
  task_run_id: string;
  status: "accepted" | "failed";
  receipt_id: string;
  production_written: false;
  created_at: string;
  finished_at: string;
}

export interface LogicAutomationListResponse {
  items: LogicAutomationPolicy[];
  count: number;
}

export interface LogicAutomationRunListResponse {
  items: LogicAutomationRun[];
  count: number;
}
