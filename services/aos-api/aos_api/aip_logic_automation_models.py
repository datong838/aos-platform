"""Tenant-scoped contracts for governed Logic automation policies."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_logic_automation_cron import validate_cron_expression


class LogicAutomationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateLogicAutomationRequest(LogicAutomationModel):
    publication_id: str
    name: str
    trigger_type: Literal["manual", "cron", "event"] = "manual"
    schedule: str = ""

    @field_validator("publication_id", "name")
    @classmethod
    def required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("field must not be empty")
        return value

    @model_validator(mode="after")
    def validate_trigger_configuration(self):
        self.schedule = self.schedule.strip()
        if self.trigger_type == "manual" and self.schedule:
            raise ValueError("manual trigger must not define schedule")
        if self.trigger_type in {"cron", "event"} and not self.schedule:
            raise ValueError("cron/event trigger requires schedule or event key")
        if self.trigger_type == "cron":
            self.schedule = validate_cron_expression(self.schedule)
        return self


class UpdateLogicAutomationRequest(LogicAutomationModel):
    expected_revision: int = Field(ge=1)
    name: str | None = None
    trigger_type: Literal["manual", "cron", "event"] | None = None
    schedule: str | None = None
    status: Literal["active", "paused"] | None = None

    @field_validator("name", "schedule")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else value

    @model_validator(mode="after")
    def validate_update_cron(self):
        if self.trigger_type == "cron" and self.schedule is not None:
            self.schedule = validate_cron_expression(self.schedule)
        return self


class LogicAutomationPolicy(LogicAutomationModel):
    automation_id: str
    graph_id: str
    publication_id: str
    graph_revision: int = Field(ge=1)
    graph_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str
    trigger_type: Literal["manual", "cron", "event"]
    schedule: str
    status: Literal["active", "paused"]
    revision: int = Field(ge=1)
    actor: str
    created_at: datetime
    updated_at: datetime


class LogicAutomationListResponse(LogicAutomationModel):
    items: list[LogicAutomationPolicy]
    count: int


class LogicAutomationRun(LogicAutomationModel):
    run_id: str
    automation_id: str
    policy_revision: int = Field(ge=1)
    trigger: Literal["manual", "cron", "event"]
    task_id: str
    task_run_id: str
    status: Literal["accepted", "failed"]
    receipt_id: str
    production_written: Literal[False] = False
    created_at: datetime
    finished_at: datetime


class LogicAutomationRunListResponse(LogicAutomationModel):
    items: list[LogicAutomationRun]
    count: int
