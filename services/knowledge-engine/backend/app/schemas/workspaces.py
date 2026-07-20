"""Private personal-workspace API contracts."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


WorkspaceTab = Literal["overview", "files", "notes", "saved", "activity"]
WorkspaceView = Literal["list", "grid"]
WorkspaceDensity = Literal["compact", "comfortable", "spacious"]
WorkspaceWidgetId = Literal[
    "storage_usage", "pinned_items", "recent_activity", "recent_notes",
    "recent_conversations", "indexing_status",
]


class WorkspacePreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: int = Field(default=1, ge=1, le=10)
    default_tab: WorkspaceTab = Field(default="files", alias="defaultTab")
    default_view: WorkspaceView = Field(default="list", alias="defaultView")
    density: WorkspaceDensity = "comfortable"
    right_rail_visible: bool = Field(default=True, alias="rightRailVisible")
    right_rail_collapsed: bool = Field(default=False, alias="rightRailCollapsed")
    visible_widgets: list[WorkspaceWidgetId] = Field(alias="visibleWidgets")
    widget_order: list[WorkspaceWidgetId] = Field(alias="widgetOrder")
    default_sort: str = Field(default="modified_desc", alias="defaultSort")
    page_size: int = Field(default=25, ge=10, le=100, alias="pageSize")
    recent_item_limit: int = Field(default=5, ge=3, le=20, alias="recentItemLimit")

    @field_validator("visible_widgets", "widget_order")
    @classmethod
    def unique_widgets(cls, value: list[WorkspaceWidgetId]) -> list[WorkspaceWidgetId]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def order_contains_visible_widgets(self) -> "WorkspacePreferences":
        missing = [widget for widget in self.visible_widgets if widget not in self.widget_order]
        self.widget_order.extend(missing)
        return self


class FolderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    folder_id: str | None = None
    pinned: bool | None = None
