/* EveOS Search Monitor bridge for the exact Local MoE Chat Sandbox conversation. */
(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search || '');
  if (!params.has('eveos_embed') || window.parent === window) return;

  const REQUEST_TYPE = 'eveos:local-moe-workspace-request';
  const EVENT_TYPE = 'eveos:local-moe-workspace-event';
  const START_TIMEOUT_MS = 12000;
  const POLL_MS = 60;
  let activeBridgeRequest = null;

  function parentOriginAllowed(origin) {
    if (origin === 'null') return true;
    try {
      const url = new URL(origin);
      return url.hostname === '127.0.0.1' || url.hostname === 'localhost' || url.hostname === '::1';
    } catch {
      return false;
    }
  }

  function reply(request, event, detail = {}) {
    const targetOrigin = request.parentOrigin === 'null' ? '*' : request.parentOrigin;
    try {
      window.parent.postMessage({
        type: EVENT_TYPE,
        workspaceId: request.workspaceId,
        requestId: request.requestId,
        event,
        ...detail
      }, targetOrigin);
    } catch (_) {}
  }

  function assistantText(node) {
    return String(node?.querySelector?.('.message-content')?.textContent || '').trim();
  }

  function lastAssistantNode(chat) {
    const nodes = chat?.querySelectorAll?.('.message.assistant') || [];
    return nodes.length ? nodes[nodes.length - 1] : null;
  }

  function currentAssistantHistoryText() {
    try {
      for (let index = conversationHistory.length - 1; index >= 0; index -= 1) {
        const item = conversationHistory[index];
        if (item?.role === 'assistant') return String(item.content || '');
      }
    } catch (_) {}
    return '';
  }

  function currentBusy() {
    try { return !!currentAbortCtrl; }
    catch { return false; }
  }

  function wasCancelled() {
    try { return userCancelledGeneration === true; }
    catch { return false; }
  }

  function startWorkspaceTurn(request) {
    if (activeBridgeRequest || currentBusy()) {
      reply(request, 'error', {
        code: 'LOCAL_MOE_WORKSPACE_BUSY',
        error: 'Local MoE is already generating in the Search Monitor Chat Sandbox.'
      });
      return;
    }

    const form = document.getElementById('chat-form');
    const prompt = document.getElementById('prompt');
    const sendButton = document.getElementById('send-btn');
    const chat = document.getElementById('chat');
    if (!form || !prompt || !sendButton || !chat) {
      reply(request, 'error', {
        code: 'LOCAL_MOE_WORKSPACE_UNAVAILABLE',
        error: 'The Local MoE Chat Sandbox is not mounted.'
      });
      return;
    }

    const priorPrompt = prompt.value;
    const assistantCountBefore = chat.querySelectorAll('.message.assistant').length;
    const historyLengthBefore = (() => {
      try { return conversationHistory.length; } catch { return 0; }
    })();
    const state = {
      ...request,
      startedAt: performance.now(),
      generationStarted: false,
      assistantNode: null,
      lastPartial: '',
      assistantCountBefore,
      historyLengthBefore,
      observer: null,
      timer: null
    };
    activeBridgeRequest = state;

    const publishPartial = () => {
      if (activeBridgeRequest !== state) return;
      if (!state.assistantNode) {
        const assistants = chat.querySelectorAll('.message.assistant');
        if (assistants.length > state.assistantCountBefore) state.assistantNode = assistants[assistants.length - 1];
      }
      const value = assistantText(state.assistantNode);
      if (value && value !== state.lastPartial) {
        state.lastPartial = value;
        reply(state, 'partial', { text: value });
      }
    };

    state.observer = new MutationObserver(publishPartial);
    state.observer.observe(chat, { childList: true, subtree: true, characterData: true });

    const finish = (kind, detail) => {
      if (activeBridgeRequest !== state) return;
      activeBridgeRequest = null;
      state.observer?.disconnect();
      if (state.timer) window.clearInterval(state.timer);
      reply(state, kind, detail);
    };

    state.timer = window.setInterval(() => {
      publishPartial();
      const busy = currentBusy();
      if (busy) {
        state.generationStarted = true;
        return;
      }
      if (state.generationStarted) {
        if (wasCancelled()) {
          finish('interrupted', {
            code: 'LOCAL_MOE_WORKSPACE_INTERRUPTED',
            error: 'Local MoE generation was stopped in the shared Search Monitor conversation.'
          });
          return;
        }
        const historyText = currentAssistantHistoryText();
        const finalText = historyText || state.lastPartial || assistantText(state.assistantNode);
        if (finalText) {
          finish('final', { text: finalText });
        } else {
          finish('error', {
            code: 'LOCAL_MOE_WORKSPACE_EMPTY',
            error: 'Local MoE completed without a visible response.'
          });
        }
        return;
      }

      if (performance.now() - state.startedAt > START_TIMEOUT_MS) {
        const assistants = chat.querySelectorAll('.message.assistant');
        const newest = assistants.length > state.assistantCountBefore ? assistants[assistants.length - 1] : null;
        const message = assistantText(newest) || 'Local MoE did not start the shared Search Monitor turn.';
        finish('error', { code: 'LOCAL_MOE_WORKSPACE_NOT_STARTED', error: message });
      }
    }, POLL_MS);

    prompt.value = String(request.text || '');
    try {
      if (typeof form.requestSubmit === 'function') form.requestSubmit(sendButton);
      else form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    } catch (error) {
      finish('error', { code: 'LOCAL_MOE_WORKSPACE_DISPATCH_FAILED', error: error.message });
    } finally {
      // The existing submit handler captures the bridge text synchronously before its first await.
      // Restore any unsent text the human had in the composer so Nexus cannot clobber it.
      window.queueMicrotask(() => {
        if (prompt.value === '' || prompt.value === String(request.text || '')) prompt.value = priorPrompt;
      });
    }
  }

  window.addEventListener('message', (event) => {
    const data = event?.data;
    if (data?.type !== REQUEST_TYPE || event.source !== window.parent || !parentOriginAllowed(event.origin)) return;
    const request = {
      workspaceId: String(data.workspaceId || ''),
      requestId: String(data.requestId || ''),
      text: String(data.text || '').trim(),
      parentOrigin: event.origin
    };
    if (!request.requestId || !request.text) {
      reply(request, 'error', {
        code: 'LOCAL_MOE_WORKSPACE_BAD_REQUEST',
        error: 'Local MoE workspace request requires requestId and text.'
      });
      return;
    }
    startWorkspaceTurn(request);
  });
})();
