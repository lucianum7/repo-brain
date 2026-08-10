from repo_brain.mcp import TOOLS, call_tool


def test_mcp_tools(tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    from repo_brain import Brain
    brain = Brain(tmp_path)
    brain.init()
    assert "brain_context" in TOOLS
    result = call_tool(brain, "brain_status", {})
    assert result["files"] >= 1

