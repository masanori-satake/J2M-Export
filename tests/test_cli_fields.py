import pytest
from j2m_export.cli import format_issue_md, format_field_value
from j2m_export.converter import MarkdownConverter

@pytest.fixture
def converter():
    return MarkdownConverter("https://jira.example.com")

def test_format_field_value():
    assert format_field_value("string") == "string"
    assert format_field_value(123) == "123"
    assert format_field_value(True) == "True"
    assert format_field_value(None) == ""
    assert format_field_value({"displayName": "User Name"}) == "User Name"
    assert format_field_value({"name": "Object Name"}) == "Object Name"
    assert format_field_value({"key": "value"}) == '{"key": "value"}'
    assert format_field_value(["label1", "label2"]) == "label1, label2"
    assert format_field_value([{"name": "A"}, {"name": "B"}]) == "A, B"
    assert format_field_value([1, 2, 3]) == "1, 2, 3"

def test_format_issue_md_basic(converter):
    issue = {
        "key": "PROJ-1",
        "fields": {
            "summary": "Issue Summary",
            "project": {"key": "PROJ", "name": "Project Name"},
            "status": {"name": "Open"},
            "assignee": {"displayName": "John Doe"},
            "created": "2024-01-01T00:00:00.000+0000",
            "description": "Some description"
        },
        "names": {
            "summary": "Summary",
            "project": "Project",
            "status": "Status",
            "assignee": "Assignee",
            "created": "Created"
        },
        "schema": {
            "summary": {"type": "string"},
            "project": {"type": "project"},
            "status": {"type": "status"},
            "assignee": {"type": "user"},
            "created": {"type": "datetime"}
        }
    }

    md = format_issue_md(issue, converter, "https://jira.example.com")

    assert "# Issue Summary" in md
    assert "- **Key**: PROJ-1" in md
    assert "- **Project**: PROJ" in md or "- **Project**: Project Name" in md
    assert "- **Status**: Open" in md
    assert "- **Assignee**: John Doe" in md
    assert "- **Created**: 2024-01-01T00:00:00.000+0000" in md
    assert "## Description" in md
    assert "Some description" in md

def test_format_issue_md_with_standard_fields(converter):
    issue = {
        "key": "PROJ-1",
        "fields": {
            "summary": "Issue Summary",
            "project": {"name": "Project Name"},
            "status": {"name": "Open"},
            "assignee": {"displayName": "John Doe"},
            "created": "2024-01-01",
            "priority": {"name": "High"},
            "labels": ["alpha", "beta"],
            "customfield_10001": "hidden"
        },
        "names": {
            "priority": "Priority",
            "labels": "Labels",
            "customfield_10001": "My Custom Field"
        },
        "schema": {
            "priority": {"type": "priority", "custom": False},
            "labels": {"type": "array", "items": "string", "custom": False},
            "customfield_10001": {"type": "string", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:textfield"}
        }
    }

    md = format_issue_md(issue, converter, "https://jira.example.com")

    assert "- **Priority**: High" in md
    assert "- **Labels**: alpha, beta" in md
    assert "My Custom Field" not in md

def test_format_issue_md_exclude_fields(converter):
    issue = {
        "key": "PROJ-1",
        "fields": {
            "summary": "Issue Summary",
            "project": {"name": "Project Name"},
            "status": {"name": "Open"},
            "assignee": {"displayName": "John Doe"},
            "created": "2024-01-01",
            "priority": {"name": "High"},
            "reporter": {"displayName": "Jane Doe"}
        },
        "names": {
            "priority": "Priority",
            "reporter": "Reporter"
        },
        "schema": {
            "priority": {"custom": False},
            "reporter": {"custom": False}
        }
    }

    # Exclude priority
    md = format_issue_md(issue, converter, "https://jira.example.com", exclude_fields=["priority"])

    assert "- **Priority**: High" not in md
    assert "- **Reporter**: Jane Doe" in md

    # Try to exclude mandatory field
    md_mandatory = format_issue_md(issue, converter, "https://jira.example.com", exclude_fields=["status"])
    assert "- **Status**: Open" in md_mandatory
