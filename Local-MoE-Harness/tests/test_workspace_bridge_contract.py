from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_workspace_bridge_is_loaded_after_the_normal_chat_pipeline():
    index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    app_pos = index.index('/static/app.js')
    bridge_pos = index.index('/static/workspace-bridge.js')
    assert app_pos < bridge_pos


def test_nexus_workspace_bridge_reuses_chat_form_and_committed_history():
    bridge = (ROOT / "web" / "workspace-bridge.js").read_text(encoding="utf-8")
    assert "document.getElementById('chat-form')" in bridge
    assert "form.requestSubmit(sendButton)" in bridge
    assert "assistantHistoryTextSince(state.historyLengthBefore)" in bridge
    assert "conversationHistory.length" in bridge
    assert "LOCAL_MOE_WORKSPACE_UNCOMMITTED" in bridge
    assert "currentAssistantHistoryText" not in bridge


def test_workspace_bridge_never_calls_the_model_api_directly():
    bridge = (ROOT / "web" / "workspace-bridge.js").read_text(encoding="utf-8")
    assert "/api/chat/stream" not in bridge
    assert "fetch(" not in bridge
    assert "eveos:local-moe-workspace-request" in bridge
    assert "eveos:local-moe-workspace-event" in bridge
