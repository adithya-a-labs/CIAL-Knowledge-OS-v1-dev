from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.workspaces import WorkspacePreferences


def valid_preferences(**overrides):
    payload = {
        "version": 1,
        "defaultTab": "files",
        "defaultView": "list",
        "density": "comfortable",
        "rightRailVisible": True,
        "rightRailCollapsed": False,
        "visibleWidgets": ["storage_usage", "pinned_items"],
        "widgetOrder": ["storage_usage"],
        "defaultSort": "modified_desc",
        "pageSize": 25,
        "recentItemLimit": 5,
    }
    payload.update(overrides)
    return payload


def test_preferences_use_stable_aliases_and_complete_widget_order():
    preferences = WorkspacePreferences.model_validate(valid_preferences())

    assert preferences.default_tab == "files"
    assert preferences.widget_order == ["storage_usage", "pinned_items"]
    assert preferences.model_dump(by_alias=True)["rightRailVisible"] is True


def test_preferences_reject_component_names_and_unknown_fields():
    with pytest.raises(ValidationError):
        WorkspacePreferences.model_validate(valid_preferences(visibleWidgets=["StorageCard"]))

    with pytest.raises(ValidationError):
        WorkspacePreferences.model_validate(valid_preferences(owner_user_id="spoofed"))


def test_preferences_bound_page_and_recent_limits():
    with pytest.raises(ValidationError):
        WorkspacePreferences.model_validate(valid_preferences(pageSize=500))

    with pytest.raises(ValidationError):
        WorkspacePreferences.model_validate(valid_preferences(recentItemLimit=1))
