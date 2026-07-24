"""Test cases for Pipeline UI Components engine."""
from __future__ import annotations

import pytest

from aos_api.pipeline_ui_components import (
    _MAX_HISTORY,
    _MAX_LAYOUTS,
    _MAX_PROPOSALS,
    PipelineLayout,
    PipelineLayoutEngine,
    PipelineProposal,
    PipelineUIComponentsError,
    SidebarItem,
    ToolbarItem,
)


class TestPipelineLayoutEngine:
    def setup_method(self) -> None:
        self.engine = PipelineLayoutEngine()

    def test_create_layout_success(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        result = self.engine.create_layout(layout)
        assert result.id.startswith("layout-")
        assert result.pipeline_id == "pipeline1"
        assert result.name == "default"

    def test_create_layout_missing_pipeline_id(self) -> None:
        layout = PipelineLayout(pipeline_id="", name="default")
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.create_layout(layout)
        assert exc_info.value.code == "MISSING_PIPELINE_ID"

    def test_create_layout_missing_name(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="")
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.create_layout(layout)
        assert exc_info.value.code == "MISSING_NAME"

    def test_get_layout_success(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        created = self.engine.create_layout(layout)
        result = self.engine.get_layout(created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_layout_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.get_layout("layout-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_layouts(self) -> None:
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline1", name="default"))
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline2", name="detailed"))
        layouts = self.engine.list_layouts()
        assert len(layouts) == 2

    def test_get_layout_by_pipeline(self) -> None:
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline1", name="default"))
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline1", name="compact"))
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline2", name="default"))
        layouts = self.engine.get_layout_by_pipeline("pipeline1")
        assert len(layouts) == 2

    def test_update_layout_success(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        created = self.engine.create_layout(layout)
        updated = self.engine.update_layout(created.id, {"name": "updated"})
        assert updated.name == "updated"

    def test_update_layout_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.update_layout("layout-nonexistent", {"name": "updated"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_layout_success(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        created = self.engine.create_layout(layout)
        result = self.engine.delete_layout(created.id)
        assert result is True

    def test_delete_layout_not_found(self) -> None:
        result = self.engine.delete_layout("layout-nonexistent")
        assert result is False

    def test_get_toolbar(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default", toolbar=[ToolbarItem(type="button", label="Run")])
        created = self.engine.create_layout(layout)
        toolbar = self.engine.get_toolbar(created.id)
        assert len(toolbar) == 1

    def test_get_toolbar_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.get_toolbar("layout-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_update_toolbar(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        created = self.engine.create_layout(layout)
        toolbar = [ToolbarItem(type="button", label="Run")]
        updated = self.engine.update_toolbar(created.id, toolbar)
        assert len(updated.toolbar) == 1

    def test_update_toolbar_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.update_toolbar("layout-nonexistent", [])
        assert exc_info.value.code == "NOT_FOUND"

    def test_get_sidebar(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default", sidebar=[SidebarItem(type="section", label="Details")])
        created = self.engine.create_layout(layout)
        sidebar = self.engine.get_sidebar(created.id)
        assert len(sidebar) == 1

    def test_get_sidebar_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.get_sidebar("layout-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_update_sidebar(self) -> None:
        layout = PipelineLayout(pipeline_id="pipeline1", name="default")
        created = self.engine.create_layout(layout)
        sidebar = [SidebarItem(type="section", label="Details")]
        updated = self.engine.update_sidebar(created.id, sidebar)
        assert len(updated.sidebar) == 1

    def test_update_sidebar_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.update_sidebar("layout-nonexistent", [])
        assert exc_info.value.code == "NOT_FOUND"

    def test_layout_fifo_eviction(self) -> None:
        for i in range(_MAX_LAYOUTS + 5):
            self.engine.create_layout(PipelineLayout(pipeline_id=f"pipeline{i}", name=f"layout{i}"))
        assert len(self.engine.list_layouts()) == _MAX_LAYOUTS

    def test_create_proposal_success(self) -> None:
        proposal = PipelineProposal(pipeline_id="pipeline1", title="Review changes")
        result = self.engine.create_proposal(proposal)
        assert result.id.startswith("prop-")
        assert result.pipeline_id == "pipeline1"
        assert result.title == "Review changes"

    def test_create_proposal_missing_pipeline_id(self) -> None:
        proposal = PipelineProposal(pipeline_id="", title="title")
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.create_proposal(proposal)
        assert exc_info.value.code == "MISSING_PIPELINE_ID"

    def test_create_proposal_missing_title(self) -> None:
        proposal = PipelineProposal(pipeline_id="pipeline1", title="")
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.create_proposal(proposal)
        assert exc_info.value.code == "MISSING_TITLE"

    def test_get_proposal_success(self) -> None:
        proposal = PipelineProposal(pipeline_id="pipeline1", title="title")
        created = self.engine.create_proposal(proposal)
        result = self.engine.get_proposal(created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_proposal_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.get_proposal("prop-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_proposals(self) -> None:
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline1", title="title1"))
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline2", title="title2"))
        proposals = self.engine.list_proposals()
        assert len(proposals) == 2

    def test_list_proposals_by_pipeline_id(self) -> None:
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline1", title="title1"))
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline1", title="title2"))
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline2", title="title3"))
        proposals = self.engine.list_proposals(pipeline_id="pipeline1")
        assert len(proposals) == 2

    def test_list_proposals_by_status(self) -> None:
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline1", title="title1"))
        self.engine.create_proposal(PipelineProposal(pipeline_id="pipeline2", title="title2"))
        proposals = self.engine.list_proposals(status="draft")
        assert len(proposals) >= 1

    def test_update_proposal_success(self) -> None:
        proposal = PipelineProposal(pipeline_id="pipeline1", title="title")
        created = self.engine.create_proposal(proposal)
        updated = self.engine.update_proposal(created.id, {"title": "Updated"})
        assert updated.title == "Updated"

    def test_update_proposal_not_found(self) -> None:
        with pytest.raises(PipelineUIComponentsError) as exc_info:
            self.engine.update_proposal("prop-nonexistent", {"title": "Updated"})
        assert exc_info.value.code == "NOT_FOUND"

    def test_delete_proposal_success(self) -> None:
        proposal = PipelineProposal(pipeline_id="pipeline1", title="title")
        created = self.engine.create_proposal(proposal)
        result = self.engine.delete_proposal(created.id)
        assert result is True

    def test_delete_proposal_not_found(self) -> None:
        result = self.engine.delete_proposal("prop-nonexistent")
        assert result is False

    def test_proposal_fifo_eviction(self) -> None:
        for i in range(_MAX_PROPOSALS + 5):
            self.engine.create_proposal(PipelineProposal(pipeline_id=f"pipeline{i}", title=f"title{i}"))
        assert len(self.engine.list_proposals()) == _MAX_PROPOSALS

    def test_list_history(self) -> None:
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline1", name="default"))
        history = self.engine.list_history()
        assert len(history) >= 1

    def test_list_history_by_pipeline_id(self) -> None:
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline1", name="default"))
        self.engine.create_layout(PipelineLayout(pipeline_id="pipeline2", name="default"))
        history = self.engine.list_history(pipeline_id="pipeline1")
        assert len(history) >= 1

    def test_history_fifo_eviction(self) -> None:
        for i in range(_MAX_HISTORY + 5):
            self.engine.create_layout(PipelineLayout(pipeline_id=f"pipeline{i}", name=f"layout{i}"))
        history = self.engine.list_history()
        assert len(history) <= _MAX_HISTORY
