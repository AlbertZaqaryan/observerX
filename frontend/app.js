// observerX_ai — frontend logic
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const emptyState = $("empty-state");
  const inputEl = $("input");
  const sendBtn = $("send-btn");
  const attachBtn = $("attach-btn");
  const fileInput = $("file-input");
  const attachmentsEl = $("attachments");
  const newChatBtn = $("new-chat");

  let pendingFiles = [];      // File objects staged for the next message
  let history = [];           // [{role, content}] text-only conversation memory
  let streaming = false;
  let cfg = { vision_enabled: true, audio_enabled: true, max_upload_mb: 50 };

  // ---------- Markdown rendering (with safe fallback) ----------
  function renderMarkdown(text) {
    if (window.marked && window.DOMPurify) {
      return window.DOMPurify.sanitize(window.marked.parse(text));
    }
    const escaped = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    return escaped.replace(/\n/g, "<br>");
  }

  // ---------- Config + health ----------
  async function loadConfig() {
    try {
      const r = await fetch("/api/config");
      cfg = await r.json();
      $("model-name").textContent = cfg.model_name || "Model";
      const caps = $("capabilities");
      const items = ["💬 Text chat", "📄 Documents & code"];
      if (cfg.vision_enabled) items.push("🖼️ Image understanding");
      if (cfg.audio_enabled) items.push("🎤 Audio transcription");
      caps.innerHTML = items.map((t) => `<li>${t}</li>`).join("");
    } catch (e) {
      $("model-name").textContent = "Model";
    }
  }

  async function pollHealth() {
    const dot = $("status-dot");
    const txt = $("status-text");
    try {
      const r = await fetch("/api/health");
      const ok = r.status === 200;
      dot.className = "status-dot " + (ok ? "ok" : "");
      txt.textContent = ok ? "ready" : "model loading…";
    } catch {
      dot.className = "status-dot down";
      txt.textContent = "offline";
    }
  }

  // ---------- Attachments ----------
  function humanSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / 1024 / 1024).toFixed(1) + " MB";
  }

  function renderAttachments() {
    attachmentsEl.innerHTML = "";
    pendingFiles.forEach((file, idx) => {
      const item = document.createElement("div");
      item.className = "attach-item";
      if (file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        item.appendChild(img);
      } else {
        const icon = document.createElement("span");
        icon.textContent = file.type.startsWith("audio/") ? "🎤" : "📄";
        item.appendChild(icon);
      }
      const label = document.createElement("span");
      label.textContent = `${file.name} · ${humanSize(file.size)}`;
      item.appendChild(label);

      const remove = document.createElement("button");
      remove.className = "remove";
      remove.textContent = "✕";
      remove.title = "Remove";
      remove.onclick = () => {
        pendingFiles.splice(idx, 1);
        renderAttachments();
      };
      item.appendChild(remove);
      attachmentsEl.appendChild(item);
    });
  }

  attachBtn.onclick = () => fileInput.click();
  fileInput.onchange = () => {
    const limit = (cfg.max_upload_mb || 50) * 1024 * 1024;
    for (const f of fileInput.files) {
      if (f.size > limit) {
        alert(`"${f.name}" is larger than the ${cfg.max_upload_mb} MB limit.`);
        continue;
      }
      pendingFiles.push(f);
    }
    fileInput.value = "";
    renderAttachments();
  };

  // ---------- Message rendering ----------
  function addMessage(role, { text = "", files = [] } = {}) {
    emptyState.style.display = "none";
    const msg = document.createElement("div");
    msg.className = `msg ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "You" : "◎";
    avatar.style.fontSize = role === "user" ? "11px" : "16px";

    const bubbleWrap = document.createElement("div");
    bubbleWrap.style.minWidth = "0";

    if (files.length) {
      const fwrap = document.createElement("div");
      fwrap.className = "msg-files";
      files.forEach((f) => {
        if (f.type.startsWith("image/")) {
          const img = document.createElement("img");
          img.src = URL.createObjectURL(f);
          fwrap.appendChild(img);
        } else {
          const chip = document.createElement("span");
          chip.className = "file-chip";
          chip.textContent = (f.type.startsWith("audio/") ? "🎤 " : "📄 ") + f.name;
          fwrap.appendChild(chip);
        }
      });
      bubbleWrap.appendChild(fwrap);
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    if (text) bubble.innerHTML = renderMarkdown(text);
    bubbleWrap.appendChild(bubble);

    msg.appendChild(avatar);
    msg.appendChild(bubbleWrap);
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return bubble;
  }

  // ---------- Sending ----------
  async function send() {
    if (streaming) return;
    const text = inputEl.value.trim();
    if (!text && pendingFiles.length === 0) return;

    const filesToSend = pendingFiles.slice();
    addMessage("user", { text, files: filesToSend });

    const form = new FormData();
    form.append("message", text);
    form.append("history", JSON.stringify(history));
    filesToSend.forEach((f) => form.append("files", f, f.name));

    // Record user turn (text summary for context).
    const userContextText = text || "[attachment only]";

    // Reset composer.
    inputEl.value = "";
    inputEl.style.height = "auto";
    pendingFiles = [];
    renderAttachments();

    const assistantBubble = addMessage("assistant", {});
    assistantBubble.classList.add("blinking-cursor");
    setStreaming(true);

    let acc = "";
    try {
      const resp = await fetch("/api/chat", { method: "POST", body: form });
      if (!resp.ok || !resp.body) {
        throw new Error(`Request failed (${resp.status})`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sep;
        while ((sep = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const line = chunk.split("\n").find((l) => l.startsWith("data:"));
          if (!line) continue;
          let evt;
          try {
            evt = JSON.parse(line.slice(5).trim());
          } catch {
            continue;
          }
          if (evt.delta) {
            acc += evt.delta;
            assistantBubble.innerHTML = renderMarkdown(acc);
            messagesEl.scrollTop = messagesEl.scrollHeight;
          } else if (evt.error) {
            acc += `\n\n**⚠️ Error:** ${evt.error}`;
            assistantBubble.innerHTML = renderMarkdown(acc);
          }
        }
      }
    } catch (err) {
      acc = acc || `⚠️ ${err.message}`;
      assistantBubble.innerHTML = renderMarkdown(acc);
    } finally {
      assistantBubble.classList.remove("blinking-cursor");
      setStreaming(false);
      // Update conversation memory.
      history.push({ role: "user", content: userContextText });
      if (acc.trim()) history.push({ role: "assistant", content: acc });
    }
  }

  function setStreaming(on) {
    streaming = on;
    sendBtn.disabled = on;
    sendBtn.textContent = on ? "…" : "Send";
  }

  // ---------- Input behaviors ----------
  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 200) + "px";
  });
  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });
  sendBtn.onclick = send;

  newChatBtn.onclick = () => {
    if (streaming) return;
    history = [];
    pendingFiles = [];
    renderAttachments();
    messagesEl.querySelectorAll(".msg").forEach((m) => m.remove());
    emptyState.style.display = "";
  };

  // ---------- Init ----------
  loadConfig();
  pollHealth();
  setInterval(pollHealth, 10000);
})();
