/**
 * Giao diện người dùng Trợ Lý AI trên Windows (Desktop Web UI).
 * Chạy 100% offline không phụ thuộc internet hay CDN bên ngoài.
 */

// =============================================================================
// CẤU HÌNH & QUẢN LÝ PHIÊN LÀM VIỆC (SESSION & STATE)
// =============================================================================

const state = {
    token: new URLSearchParams(window.location.search).get("token") || localStorage.getItem("troly_session_token") || "",
    currentConversationId: null,
    currentScreen: "chat",
    ws: null,
    isGenerating: false,
    currentAssistantRow: null,
    currentTextSpan: null,
    approvalTimerInterval: null,
    activeApprovalRequestId: null,
};

if (state.token) {
    localStorage.setItem("troly_session_token", state.token);
}

// =============================================================================
// BỘ PHÂN TÍCH MARKDOWN THUẦN TÚY (OFFLINE SAFE MARKDOWN PARSER)
// =============================================================================

function escapeHtml(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function parseMarkdown(mdText) {
    if (!mdText) return "";

    // 1. Tách và bảo vệ khối code trước (Code blocks ```...```)
    const codeBlocks = [];
    let processed = mdText.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
        const id = `__CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push({ lang: lang || "text", code: escapeHtml(code.trim()) });
        return id;
    });

    // 2. Bảo vệ inline code `...`
    const inlineCodes = [];
    processed = processed.replace(/`([^`]+)`/g, (match, code) => {
        const id = `__INLINE_CODE_${inlineCodes.length}__`;
        inlineCodes.push(escapeHtml(code));
        return id;
    });

    // 3. Xử lý bảng Markdown (| Header 1 | Header 2 |\n|---|---|\n| Cell 1 | Cell 2 |) trước khi escape
    const tables = [];
    processed = processed.replace(/((?:\|[^\n]+\|\r?\n)((?:\|(?:\s*[:-]+[-| :]*)\|\r?\n))((?:\|[^\n]+\|\r?\n?)+))/g, (match, headerLine, sepLine, rowsBlock) => {
        const id = `__TABLE_BLOCK_${tables.length}__`;
        const parseRow = (line, tag) => {
            const cells = line.split('|').slice(1, -1);
            return '<tr>' + cells.map(c => `<${tag}>${escapeHtml(c.trim())}</${tag}>`).join('') + '</tr>';
        };
        const thead = '<thead>' + parseRow(headerLine.trim(), 'th') + '</thead>';
        const rows = rowsBlock.trim().split(/\r?\n/).map(r => parseRow(r.trim(), 'td')).join('');
        const tbody = '<tbody>' + rows + '</tbody>';
        tables.push(`<div class="table-container"><table class="markdown-table">${thead}${tbody}</table></div>`);
        return id;
    });

    // 4. Escape HTML cho các phần còn lại để chống XSS
    processed = escapeHtml(processed);

    // 5. Liên kết Markdown [Tiêu đề](https://...)
    processed = processed.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // 6. Định dạng tiêu đề (Headings)
    processed = processed.replace(/^### (.*$)/gim, "<h3>$1</h3>");
    processed = processed.replace(/^## (.*$)/gim, "<h2>$1</h2>");
    processed = processed.replace(/^# (.*$)/gim, "<h1>$1</h1>");

    // 7. In đậm & in nghiêng
    processed = processed.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    processed = processed.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // 8. Blockquote
    processed = processed.replace(/^\> (.*$)/gim, "<blockquote>$1</blockquote>");

    // 9. Danh sách không thứ tự (* hoặc -)
    processed = processed.replace(/^\s*[-*]\s+(.*$)/gim, "<li>$1</li>");
    processed = processed.replace(/(<li>.*<\/li>)/gim, "<ul>$1</ul>");

    // 10. Đổi dòng đơn sang <br> (nếu không phải trong thẻ block)
    processed = processed.replace(/\n/g, "<br>");

    // 11. Khôi phục lại bảng dữ liệu
    tables.forEach((tbl, idx) => {
        processed = processed.replace(`__TABLE_BLOCK_${idx}__`, tbl);
    });

    // 12. Khôi phục lại inline code
    inlineCodes.forEach((code, idx) => {
        processed = processed.replace(`__INLINE_CODE_${idx}__`, `<code>${code}</code>`);
    });

    // 13. Khôi phục lại khối code blocks
    codeBlocks.forEach((block, idx) => {
        const blockHtml = `
            <div class="code-container">
                <div class="code-header">
                    <span class="code-lang">${escapeHtml(block.lang)}</span>
                    <button class="btn-copy-code" onclick="copyCodeSnippet(this)">Sao chép</button>
                </div>
                <pre><code class="lang-${block.lang}">${block.code}</code></pre>
            </div>
        `;
        processed = processed.replace(`__CODE_BLOCK_${idx}__`, blockHtml);
    });

    // 14. Bảo mật: Làm sạch toàn bộ HTML bằng DOMPurify nếu có
    if (typeof window !== "undefined" && window.DOMPurify && typeof window.DOMPurify.sanitize === "function") {
        processed = window.DOMPurify.sanitize(processed);
    }

    return processed;
}


function copyCodeSnippet(button) {
    const container = button.closest(".code-container");
    if (!container) return;
    const codeElem = container.querySelector("pre code");
    if (codeElem) {
        navigator.clipboard.writeText(codeElem.innerText).then(() => {
            const oldText = button.innerText;
            button.innerText = "Đã chép!";
            setTimeout(() => { button.innerText = oldText; }, 1500);
        }).catch(() => {
            button.innerText = "Lỗi!";
        });
    }
}

// =============================================================================
// YÊU CẦU REST API CÓ BẢO VỆ TOKEN
// =============================================================================


async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    headers["X-Session-Token"] = state.token;

    const url = endpoint.includes("?") 
        ? `${endpoint}&token=${encodeURIComponent(state.token)}`
        : `${endpoint}?token=${encodeURIComponent(state.token)}`;

    const resp = await fetch(url, { ...options, headers });
    if (!resp.ok) {
        if (resp.status === 401 || resp.status === 403) {
            console.error("Session Token không hợp lệ:", resp.status);
        }
        const errJson = await resp.json().catch(() => ({}));
        throw new Error(errJson.detail || `Lỗi máy chủ (${resp.status})`);
    }
    return resp.json();
}

// =============================================================================
// KẾT NỐI VÀ QUẢN LÝ WEBSOCKET
// =============================================================================

function connectWebSocket() {
    const statusDot = document.getElementById("status-dot");
    const statusText = document.getElementById("status-text");

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/chat?token=${encodeURIComponent(state.token)}`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        statusDot.className = "status-dot online";
        statusText.innerText = "Đã kết nối";
    };

    state.ws.onclose = (event) => {
        statusDot.className = "status-dot offline";
        if (event.code === 1008 || (event.reason && event.reason.includes("token"))) {
            statusText.innerText = "Phiên làm việc đã hết hạn. Vui lòng F5 tải lại trang.";
            return;
        }
        statusText.innerText = "Mất kết nối (Đang thử lại...)";
        // Tự động kết nối lại sau 2 giây
        setTimeout(connectWebSocket, 2000);
    };

    state.ws.onerror = (err) => {
        console.error("Lỗi WebSocket:", err);
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleServerEvent(msg.type, msg.data || {});
        } catch (e) {
            console.error("Không thể xử lý tin nhắn WebSocket:", e);
        }
    };
}

function handleServerEvent(type, data) {
    const chatContainer = document.getElementById("chat-messages");

    switch (type) {
        case "text_delta":
            if (state.currentTextSpan) {
                state.currentRawText = (state.currentRawText || "") + data.content;
                state.currentTextSpan.innerHTML = parseMarkdown(state.currentRawText);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            break;

        case "tool_start":
            if (state.currentAssistantRow) {
                let metaBox = state.currentAssistantRow.querySelector(".message-meta");
                if (!metaBox) {
                    metaBox = document.createElement("div");
                    metaBox.className = "message-meta";
                    state.currentAssistantRow.querySelector(".message-bubble").appendChild(metaBox);
                }
                const pill = document.createElement("span");
                pill.className = "meta-badge tool";
                pill.id = `tool-pill-${data.tool_name}`;
                pill.innerHTML = `⚙️ Đang chạy: <strong>${escapeHtml(data.tool_name)}</strong>...`;
                metaBox.appendChild(pill);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            break;

        case "tool_result":
            const existingPill = document.getElementById(`tool-pill-${data.tool_name}`);
            if (existingPill) {
                if (data.is_error) {
                    existingPill.className = "meta-badge danger";
                    existingPill.innerHTML = `❌ Lỗi: <strong>${escapeHtml(data.tool_name)}</strong>`;
                } else {
                    existingPill.className = "meta-badge";
                    existingPill.innerHTML = `✅ Xong: <strong>${escapeHtml(data.tool_name)}</strong>`;
                }
            }
            break;

        case "approval_required":
            showApprovalModal(data);
            break;

        case "turn_done":
            finishCurrentTurn(data);
            break;

        case "error":
            appendErrorMessage(data.error);
            finishCurrentTurn({});
            break;
    }
}

// =============================================================================
// GIAO DIỆN CHAT & STREAMING
// =============================================================================

function sendUserMessage() {
    const textarea = document.getElementById("user-input");
    const text = textarea.value.trim();
    if (!text || state.isGenerating) return;

    textarea.value = "";
    textarea.style.height = "auto";

    // 1. Append user message to UI
    appendUserBubble(text);

    // 2. Prepare assistant placeholder bubble
    prepareAssistantBubble();

    // 3. Send over WebSocket
    const modeSelect = document.getElementById("select-model-mode");
    const chkSensitive = document.getElementById("chk-sensitive");

    const payload = {
        type: "user_message",
        message: text,
        conversation_id: state.currentConversationId,
        mode: modeSelect.value,
        is_sensitive: chkSensitive.checked,
    };

    state.isGenerating = true;
    document.getElementById("btn-send").classList.add("hidden");
    document.getElementById("btn-cancel").classList.remove("hidden");

    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify(payload));
    } else {
        appendErrorMessage("Mất kết nối tới máy chủ. Đang chờ kết nối lại...");
        finishCurrentTurn({});
    }
}

function appendUserBubble(text) {
    const chatContainer = document.getElementById("chat-messages");
    const row = document.createElement("div");
    row.className = "message-row user";
    row.innerHTML = `
        <div class="message-bubble">
            <div class="message-text">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
        </div>
    `;
    chatContainer.appendChild(row);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function prepareAssistantBubble() {
    const chatContainer = document.getElementById("chat-messages");
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-bubble">
            <div class="message-text typing-cursor"></div>
        </div>
    `;
    chatContainer.appendChild(row);

    state.currentAssistantRow = row;
    state.currentTextSpan = row.querySelector(".message-text");
    state.currentRawText = "";
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function finishCurrentTurn(data) {
    state.isGenerating = false;
    document.getElementById("btn-send").classList.remove("hidden");
    document.getElementById("btn-cancel").classList.remove("hidden");
    document.getElementById("btn-cancel").classList.add("hidden");

    if (state.currentTextSpan) {
        state.currentTextSpan.classList.remove("typing-cursor");
        if (!state.currentRawText) {
            state.currentTextSpan.innerHTML = `<span class="text-muted">${data.cancelled ? "⏹ Đã dừng câu trả lời theo yêu cầu." : "⚠️ Chưa nhận được phản hồi từ mô hình."}</span>`;
        }
    }

    if (data.model_used && state.currentAssistantRow) {
        let metaBox = state.currentAssistantRow.querySelector(".message-meta");
        if (!metaBox) {
            metaBox = document.createElement("div");
            metaBox.className = "message-meta";
            state.currentAssistantRow.querySelector(".message-bubble").appendChild(metaBox);
        }
        const modelBadge = document.createElement("span");
        modelBadge.className = "meta-badge";
        modelBadge.innerText = `🏷️ ${data.model_used}`;
        metaBox.prepend(modelBadge);
    }

    if (data.conversation_id && !state.currentConversationId) {
        state.currentConversationId = data.conversation_id;
        loadConversations();
    }

    state.currentAssistantRow = null;
    state.currentTextSpan = null;
    state.currentRawText = "";
}

function appendErrorMessage(errText) {
    const chatContainer = document.getElementById("chat-messages");
    const row = document.createElement("div");
    row.className = "message-row assistant";
    row.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div class="message-bubble" style="border-color: var(--danger);">
            <div class="message-text" style="color: var(--danger);">Lỗi: ${escapeHtml(errText)}</div>
        </div>
    `;
    chatContainer.appendChild(row);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

let _approvalKeydownHandler = null;

function showApprovalModal(data) {
    state.activeApprovalRequestId = data.request_id;
    const modal = document.getElementById("approval-modal");
    document.getElementById("approval-tool-name").innerText = data.tool_name || "-";
    document.getElementById("approval-reason").innerText = data.reason || "-";
    document.getElementById("approval-args").innerText = JSON.stringify(data.arguments || {}, null, 2);

    let timeLeft = 120;
    const timerElem = document.getElementById("approval-timer");
    timerElem.innerText = timeLeft;

    clearInterval(state.approvalTimerInterval);
    state.approvalTimerInterval = setInterval(() => {
        timeLeft -= 1;
        timerElem.innerText = timeLeft;
        if (timeLeft <= 0) {
            clearInterval(state.approvalTimerInterval);
            respondApproval(false);
        }
    }, 1000);

    modal.classList.remove("hidden");

    // 1. Tự động focus nút Từ chối (Safety first)
    const btnDeny = document.getElementById("btn-deny-approval");
    const btnApprove = document.getElementById("btn-approve-approval");
    if (btnDeny) {
        btnDeny.focus();
    }

    // 2. Khóa tiêu điểm (Focus Trap) & Phím tắt an toàn: Esc = Từ chối, Chặn Enter tự động duyệt
    if (_approvalKeydownHandler) {
        window.removeEventListener("keydown", _approvalKeydownHandler);
    }

    _approvalKeydownHandler = function (e) {
        if (modal.classList.contains("hidden")) return;

        // Esc -> Tương đương Từ chối
        if (e.key === "Escape") {
            e.preventDefault();
            respondApproval(false);
            return;
        }

        // Chặn phím Enter tự động Cho phép nếu không chủ động focus vào nút Cho phép
        if (e.key === "Enter" && document.activeElement !== btnApprove) {
            e.preventDefault();
            return;
        }

        // Bẫy tiêu điểm (Focus Trap giữa Deny và Approve)
        if (e.key === "Tab") {
            const focusables = [btnDeny, btnApprove].filter(Boolean);
            if (focusables.length === 0) return;
            const first = focusables[0];
            const last = focusables[focusables.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    last.focus();
                    e.preventDefault();
                }
            } else {
                if (document.activeElement === last) {
                    first.focus();
                    e.preventDefault();
                }
            }
        }
    };

    window.addEventListener("keydown", _approvalKeydownHandler);
}

function respondApproval(approved) {
    if (_approvalKeydownHandler) {
        window.removeEventListener("keydown", _approvalKeydownHandler);
        _approvalKeydownHandler = null;
    }
    clearInterval(state.approvalTimerInterval);
    document.getElementById("approval-modal").classList.add("hidden");

    // Khôi phục tiêu điểm về khung nhập tin nhắn
    const input = document.getElementById("user-input");
    if (input) input.focus();

    if (state.activeApprovalRequestId && state.ws) {
        const payload = {
            type: "approval_response",
            request_id: state.activeApprovalRequestId,
            approved: approved,
        };
        state.ws.send(JSON.stringify(payload));
        state.activeApprovalRequestId = null;
    }
}


// =============================================================================
// QUẢN LÝ DANH SÁCH CUỘC HỘI THOẠI
// =============================================================================

async function loadConversations() {
    try {
        const convs = await apiFetch("/api/conversations");
        const select = document.getElementById("select-conversations");
        select.innerHTML = '<option value="">(Chọn cuộc trò chuyện)</option>';

        convs.forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c.id;
            opt.innerText = c.title || "Cuộc trò chuyện";
            if (c.id === state.currentConversationId) {
                opt.selected = true;
            }
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Không thể tải danh sách hội thoại:", e);
    }
}

async function loadConversationMessages(convId) {
    try {
        const msgs = await apiFetch(`/api/conversations/${convId}/messages`);
        const chatContainer = document.getElementById("chat-messages");
        chatContainer.innerHTML = "";

        msgs.forEach((m) => {
            if (m.role === "user") {
                appendUserBubble(m.content);
            } else if (m.role === "assistant") {
                const row = document.createElement("div");
                row.className = "message-row assistant";
                row.innerHTML = `
                    <div class="message-avatar">🤖</div>
                    <div class="message-bubble">
                        <div class="message-text">${parseMarkdown(m.content)}</div>
                        ${m.model_used ? `<div class="message-meta"><span class="meta-badge">🏷️ ${escapeHtml(m.model_used)}</span></div>` : ""}
                    </div>
                `;
                chatContainer.appendChild(row);
            }
        });
        chatContainer.scrollTop = chatContainer.scrollHeight;
    } catch (e) {
        console.error("Không thể tải tin nhắn hội thoại:", e);
    }
}

// =============================================================================
// QUẢN LÝ TRÍ NHỚ DÀI HẠN (MEMORIES VIEW)
// =============================================================================

async function loadMemories(query = "", category = "") {
    try {
        let url = "/api/memories?";
        if (query) url += `query=${encodeURIComponent(query)}&`;
        if (category) url += `category=${encodeURIComponent(category)}&`;

        const memories = await apiFetch(url);
        const grid = document.getElementById("memory-grid");
        grid.innerHTML = "";

        if (memories.length === 0) {
            grid.innerHTML = '<div style="color: var(--text-muted); padding: 2rem;">Chưa có dữ kiện trí nhớ nào phù hợp.</div>';
            return;
        }

        memories.forEach((mem) => {
            const card = document.createElement("div");
            card.className = "memory-card";
            card.innerHTML = `
                <div class="memory-card-header">
                    <span class="memory-cat-badge">${escapeHtml(mem.category)}</span>
                </div>
                <div class="memory-card-body">${escapeHtml(mem.content)}</div>
                <div class="memory-card-footer">
                    <span>${new Date(mem.updated_at).toLocaleDateString("vi-VN")}</span>
                    <div>
                        <button class="btn btn-outline btn-sm btn-edit-mem" data-id="${mem.id}">✏️ Sửa</button>
                        <button class="btn btn-outline btn-sm btn-del-mem" data-id="${mem.id}" style="color: var(--danger);">🗑️ Xoá</button>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });

        // Gắn sự kiện cho các nút Sửa & Xoá
        grid.querySelectorAll(".btn-edit-mem").forEach((btn) => {
            btn.onclick = () => {
                const mem = memories.find((m) => m.id === btn.dataset.id);
                if (mem) openEditMemoryModal(mem);
            };
        });

        grid.querySelectorAll(".btn-del-mem").forEach((btn) => {
            btn.onclick = async () => {
                if (confirm("Bạn có chắc chắn muốn xoá mục trí nhớ này không?")) {
                    await apiFetch(`/api/memories/${btn.dataset.id}`, { method: "DELETE" });
                    loadMemories();
                }
            };
        });
    } catch (e) {
        console.error("Không thể nạp trí nhớ:", e);
    }
}

function openEditMemoryModal(mem = null) {
    const modal = document.getElementById("memory-modal");
    const title = document.getElementById("memory-modal-title");
    const idInput = document.getElementById("edit-memory-id");
    const catSelect = document.getElementById("input-memory-cat");
    const contentText = document.getElementById("input-memory-content");

    if (mem) {
        title.innerText = "Chỉnh Sửa Trí Nhớ";
        idInput.value = mem.id;
        catSelect.value = mem.category;
        contentText.value = mem.content;
    } else {
        title.innerText = "Thêm Trí Nhớ Mới";
        idInput.value = "";
        catSelect.value = "preference";
        contentText.value = "";
    }

    modal.classList.remove("hidden");
}

async function saveMemory() {
    const id = document.getElementById("edit-memory-id").value;
    const category = document.getElementById("input-memory-cat").value;
    const content = document.getElementById("input-memory-content").value.trim();

    if (!content) return alert("Vui lòng nhập nội dung dữ kiện cần ghi nhớ.");

    try {
        if (id) {
            await apiFetch(`/api/memories/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ category, content }),
            });
        } else {
            await apiFetch("/api/memories", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ category, content }),
            });
        }
        document.getElementById("memory-modal").classList.add("hidden");
        loadMemories();
    } catch (e) {
        alert("Lỗi lưu trí nhớ: " + e.message);
    }
}

// =============================================================================
// QUẢN LÝ NHẮC VIỆC (REMINDERS VIEW)
// =============================================================================

async function loadReminders() {
    try {
        const reminders = await apiFetch("/api/reminders");
        const upcomingList = document.getElementById("upcoming-reminders-list");
        const missedList = document.getElementById("missed-reminders-list");

        upcomingList.innerHTML = "";
        missedList.innerHTML = "";

        const upcoming = reminders.filter((r) => r.status === "pending" || r.status === "snoozed");
        const missed = reminders.filter((r) => r.status === "missed");

        if (upcoming.length === 0) {
            upcomingList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.88rem;">Không có lời nhắc nào sắp tới.</div>';
        } else {
            upcoming.forEach((r) => upcomingList.appendChild(createReminderCard(r, "upcoming")));
        }

        if (missed.length === 0) {
            missedList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.88rem;">Không có lời nhắc nào bị bỏ lỡ.</div>';
        } else {
            missed.forEach((r) => missedList.appendChild(createReminderCard(r, "missed")));
        }
    } catch (e) {
        console.error("Không thể tải lời nhắc việc:", e);
    }
}

function createReminderCard(rem, type) {
    const card = document.createElement("div");
    card.className = `reminder-card ${type}`;

    const dateStr = new Date(rem.trigger_at).toLocaleString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
    });

    card.innerHTML = `
        <div class="reminder-card-header">
            <span class="reminder-time">⏰ ${dateStr}</span>
            <span class="meta-badge">${escapeHtml(rem.status)}</span>
        </div>
        <div class="reminder-message">${escapeHtml(rem.message)}</div>
        <div class="reminder-actions">
            <button class="btn btn-outline btn-sm btn-snooze-rem" data-id="${rem.id}">💤 Hoãn 10p</button>
            <button class="btn btn-outline btn-sm btn-del-rem" data-id="${rem.id}" style="color: var(--danger);">🗑️ Xoá</button>
        </div>
    `;

    card.querySelector(".btn-snooze-rem").onclick = async () => {
        await apiFetch(`/api/reminders/${rem.id}/snooze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ minutes: 10 }),
        });
        loadReminders();
    };

    card.querySelector(".btn-del-rem").onclick = async () => {
        await apiFetch(`/api/reminders/${rem.id}`, { method: "DELETE" });
        loadReminders();
    };

    return card;
}

async function saveReminder() {
    const message = document.getElementById("input-reminder-message").value.trim();
    const timeVal = document.getElementById("input-reminder-time").value;

    if (!message || !timeVal) return alert("Vui lòng nhập đầy đủ nội dung và thời gian nhắc việc.");

    const isoTime = new Date(timeVal).toISOString();

    try {
        await apiFetch("/api/reminders", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, trigger_at: isoTime }),
        });
        document.getElementById("reminder-modal").classList.add("hidden");
        loadReminders();
    } catch (e) {
        alert("Lỗi tạo lời nhắc: " + e.message);
    }
}

// =============================================================================
// CÀI ĐẶT & CHẨN ĐOÁN (SETTINGS & DIAGNOSTICS)
// =============================================================================

async function loadDiagnostics() {
    try {
        const res = await apiFetch("/api/settings/diagnostics");
        if (!res) return;

        // 1. Trạng thái Gemini API Cloud
        const geminiEl = document.getElementById("diag-gemini-status");
        if (res.gemini_configured && res.gemini_reachable) {
            geminiEl.innerText = "🟢 Hoạt động tốt (Online)";
            geminiEl.className = "diag-value online";
        } else if (res.gemini_configured && !res.gemini_reachable) {
            geminiEl.innerText = "🟡 Đã có Key (Mất mạng / Không kết nối)";
            geminiEl.className = "diag-value offline";
        } else {
            geminiEl.innerText = "⚪ Chưa cài đặt API Key";
            geminiEl.className = "diag-value error";
        }

        // 2. Nguồn API Key
        document.getElementById("diag-key-source").innerText = res.gemini_key_source || "Không";

        // 3. Trạng thái Ollama cục bộ
        const ollamaEl = document.getElementById("diag-ollama-status");
        if (res.ollama_running) {
            ollamaEl.innerText = "🟢 Đang chạy (Sẵn sàng cổng 11434)";
            ollamaEl.className = "diag-value online";
        } else {
            ollamaEl.innerText = "⚪ Chưa bật (Không phản hồi port 11434)";
            ollamaEl.className = "diag-value offline";
        }

        // 4. Chế độ hiện tại
        const modeLabels = { auto: "Tự động (Auto)", gemini: "Chỉ dùng Gemini (Cloud)", local: "Chỉ dùng Cục bộ (Ollama)" };
        document.getElementById("diag-current-mode").innerText = modeLabels[res.mode] || res.mode;

        const modeSelect = document.getElementById("settings-select-mode");
        if (modeSelect) {
            modeSelect.value = res.mode;
            modeSelect.onchange = async (e) => {
                await apiFetch("/api/settings/model", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: e.target.value }),
                });
                const chatSelect = document.getElementById("select-model-mode");
                if (chatSelect) chatSelect.value = e.target.value;
                await loadDiagnostics();
            };
        }

        const chatModeSelect = document.getElementById("select-model-mode");
        if (chatModeSelect && !chatModeSelect._hasBoundChange) {
            chatModeSelect._hasBoundChange = true;
            chatModeSelect.onchange = async (e) => {
                await apiFetch("/api/settings/model", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: e.target.value }),
                });
            };
        }

        // Cập nhật tên local model trên badge và dropdown
        const activeLocal = res.local_model || "qwen2.5:14b";
        const headerBadge = document.getElementById("active-local-model-badge");
        if (headerBadge) {
            headerBadge.innerText = activeLocal;
        }

        const localModelSelect = document.getElementById("settings-select-local-model");
        if (localModelSelect) {
            localModelSelect.innerHTML = "";
            if (res.ollama_models && res.ollama_models.length > 0) {
                res.ollama_models.forEach((m) => {
                    const opt = document.createElement("option");
                    opt.value = m;
                    opt.innerText = m;
                    if (m === activeLocal || m.startsWith(activeLocal)) {
                        opt.selected = true;
                    }
                    localModelSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement("option");
                opt.value = activeLocal;
                opt.innerText = `${activeLocal} (chưa tải về)`;
                opt.selected = true;
                localModelSelect.appendChild(opt);
            }
            localModelSelect.onchange = async (e) => {
                await changeLocalModel(e.target.value);
            };
        }

        // 5. Autostart checkbox
        const autoCheck = document.getElementById("chk-autostart");
        if (autoCheck) autoCheck.checked = Boolean(res.autostart_enabled);

        // 6. Workspace path
        const wsEl = document.getElementById("settings-ws-hint");
        if (wsEl) wsEl.innerText = res.workspace_dir || "C:\\AI_Workspace";

        // 7. Danh sách model Ollama cục bộ
        const modelsList = document.getElementById("diag-ollama-models");
        if (modelsList) {
            modelsList.innerHTML = "";
            if (res.ollama_models && res.ollama_models.length > 0) {
                res.ollama_models.forEach((m) => {
                    const tag = document.createElement("span");
                    const isActive = (m === activeLocal || m.startsWith(activeLocal));
                    tag.className = "model-tag" + (isActive ? " active" : "");
                    tag.title = "Bấm để kích hoạt model này";
                    tag.innerText = m + (isActive ? " ✓" : "");
                    tag.onclick = async () => {
                        await changeLocalModel(m);
                    };
                    modelsList.appendChild(tag);
                });
            } else {
                modelsList.innerHTML = `<span class="tag-empty">${res.ollama_running ? "(Chưa có model nào. Hãy chạy: ollama pull qwen2.5:14b)" : "(Ollama chưa bật)"}</span>`;
            }
        }
    } catch (err) {
        console.error("Lỗi tải chẩn đoán:", err);
    }
}

async function changeLocalModel(newModel) {
    if (!newModel) return;
    try {
        const res = await apiFetch("/api/settings/local-model", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ local_model: newModel }),
        });
        if (res && res.ok) {
            const headerBadge = document.getElementById("active-local-model-badge");
            if (headerBadge) headerBadge.innerText = newModel;
            await loadDiagnostics();
        }
    } catch (err) {
        console.error("Lỗi cập nhật model Ollama:", err);
    }
}

async function saveGeminiKey() {
    const keyInput = document.getElementById("input-gemini-key");
    const feedback = document.getElementById("key-feedback");
    const keyVal = keyInput.value.trim();

    if (!keyVal) {
        feedback.innerText = "⚠️ Vui lòng nhập API Key hợp lệ trước khi bấm lưu.";
        feedback.className = "key-status-feedback error";
        return;
    }

    try {
        const res = await apiFetch("/api/settings/gemini-key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: keyVal }),
        });
        if (res && res.ok) {
            feedback.innerText = "✅ " + res.message;
            feedback.className = "key-status-feedback success";
            keyInput.value = "";
            loadDiagnostics();
        } else {
            feedback.innerText = "❌ Lỗi: " + (res?.detail || "Không thể lưu khóa.");
            feedback.className = "key-status-feedback error";
        }
    } catch (err) {
        feedback.innerText = "❌ Lỗi: " + err.message;
        feedback.className = "key-status-feedback error";
    }
}


// =============================================================================
// I18N ĐA NGÔN NGỮ
// =============================================================================
let _i18nData = null;

async function initI18n() {
    try {
        const resp = await fetch("/static/i18n/vi.json");
        if (resp.ok) {
            _i18nData = await resp.json();
        }
    } catch (err) {
        console.warn("Chưa nạp được vi.json, sử dụng nhãn mặc định:", err);
    }
}

function t(keyPath, fallback = "") {
    if (!_i18nData) return fallback || keyPath;
    const parts = keyPath.split(".");
    let curr = _i18nData;
    for (const part of parts) {
        if (curr && typeof curr === "object" && part in curr) {
            curr = curr[part];
        } else {
            return fallback || keyPath;
        }
    }
    return typeof curr === "string" ? curr : (fallback || keyPath);
}

// =============================================================================
// QUẢN LÝ NHẬT KÝ KIỂM TOÁN (AUDIT LOGS)
// =============================================================================

async function loadAuditLogs() {
    const tbody = document.getElementById("audit-table-body");
    if (!tbody) return;

    try {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Đang nạp nhật ký kiểm toán...</td></tr>`;
        const logs = await apiFetch("/api/audit?limit=150");
        tbody.innerHTML = "";
        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Chưa có sự kiện kiểm toán nào được ghi nhận.</td></tr>`;
            return;
        }

        logs.forEach((item) => {
            const tr = document.createElement("tr");
            const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleString("vi-VN") : "-";
            const levelClass = (item.permission_level || "info").toLowerCase();
            const levelBadge = `<span class="badge badge-${levelClass}">${escapeHtml(item.permission_level || "INFO")}</span>`;

            let statusBadge = `<span class="badge badge-success">Thành công</span>`;
            if (item.status === "DENIED" || item.status === "FAILED") {
                statusBadge = `<span class="badge badge-danger">Từ chối/Lỗi</span>`;
            } else if (item.status === "APPROVED") {
                statusBadge = `<span class="badge badge-warning">Đã duyệt</span>`;
            }

            const action = escapeHtml(item.action || item.tool_name || "event");
            const details = escapeHtml(JSON.stringify(item.details || item.arguments || {}, null, 1));

            tr.innerHTML = `
                <td class="col-time">${timeStr}</td>
                <td class="col-action"><strong>${action}</strong></td>
                <td class="col-level">${levelBadge}</td>
                <td class="col-status">${statusBadge}</td>
                <td class="col-details"><pre class="audit-details-box">${details}</pre></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="5" class="error-state">Lỗi khi tải nhật ký: ${escapeHtml(err.message)}</td></tr>`;
    }
}

// =============================================================================
// KHỞI TẠO VÀ LẮNG NGHE SỰ KIỆN (INITIALIZATION)
// =============================================================================

document.addEventListener("DOMContentLoaded", async () => {
    await initI18n();

    // 1. Chuyển đổi màn hình (Sidebar navigation)
    document.querySelectorAll(".nav-item").forEach((btn) => {
        btn.onclick = () => {
            document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".screen-view").forEach((s) => s.classList.remove("active"));

            btn.classList.add("active");
            const screenId = `screen-${btn.dataset.screen}`;
            const targetScreen = document.getElementById(screenId);
            if (targetScreen) targetScreen.classList.add("active");
            state.currentScreen = btn.dataset.screen;

            if (state.currentScreen === "memories") loadMemories();
            if (state.currentScreen === "reminders") loadReminders();
            if (state.currentScreen === "audit") loadAuditLogs();
            if (state.currentScreen === "settings") loadDiagnostics();
        };
    });


    // 2. Chuyển đổi Dark/Light mode
    const themeBtn = document.getElementById("theme-toggle");
    const themeIcon = document.getElementById("theme-icon");
    const savedTheme = localStorage.getItem("troly_theme") || "dark";
    if (savedTheme === "light") {
        document.body.className = "light-theme";
        themeIcon.innerText = "☀️";
    }

    themeBtn.onclick = () => {
        if (document.body.classList.contains("dark-theme")) {
            document.body.className = "light-theme";
            themeIcon.innerText = "☀️";
            localStorage.setItem("troly_theme", "light");
        } else {
            document.body.className = "dark-theme";
            themeIcon.innerText = "🌙";
            localStorage.setItem("troly_theme", "dark");
        }
    };

    // 3. Tự động co giãn textarea chat
    const textarea = document.getElementById("user-input");
    textarea.addEventListener("input", () => {
        textarea.style.height = "auto";
        textarea.style.height = Math.min(textarea.scrollHeight, 180) + "px";
    });

    textarea.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendUserMessage();
        }
    });

    document.getElementById("btn-send").onclick = sendUserMessage;

    document.getElementById("btn-cancel").onclick = () => {
        if (state.ws && state.ws.readyState === WebSocket.OPEN) {
            try {
                state.ws.send(JSON.stringify({ type: "cancel" }));
            } catch (e) {
                console.error("Lỗi gửi lệnh huỷ:", e);
            }
        }
        finishCurrentTurn({ cancelled: true });
    };

    // 4. Sự kiện modal phê duyệt
    document.getElementById("btn-approve-approval").onclick = () => respondApproval(true);
    document.getElementById("btn-deny-approval").onclick = () => respondApproval(false);

    // 5. Sự kiện thêm cuộc trò chuyện mới
    document.getElementById("btn-new-chat").onclick = () => {
        state.currentConversationId = null;
        document.getElementById("select-conversations").value = "";
        document.getElementById("chat-messages").innerHTML = `
            <div class="message-row assistant">
                <div class="message-avatar">🤖</div>
                <div class="message-bubble">
                    <div class="message-text">Sẵn sàng bắt đầu cuộc trò chuyện mới! Hãy nhập yêu cầu của bạn bên dưới.</div>
                </div>
            </div>
        `;
    };

    document.getElementById("select-conversations").onchange = (e) => {
        if (e.target.value) {
            state.currentConversationId = e.target.value;
            loadConversationMessages(state.currentConversationId);
        }
    };

    // 6. Sự kiện màn hình Trí nhớ
    document.getElementById("btn-add-memory").onclick = () => openEditMemoryModal();
    document.getElementById("btn-cancel-memory").onclick = () => document.getElementById("memory-modal").classList.add("hidden");
    document.getElementById("btn-save-memory").onclick = saveMemory;

    let searchDebounce = null;
    document.getElementById("search-memory").oninput = (e) => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => {
            const cat = document.getElementById("filter-memory-category").value;
            loadMemories(e.target.value, cat);
        }, 300);
    };

    document.getElementById("filter-memory-category").onchange = (e) => {
        const query = document.getElementById("search-memory").value;
        loadMemories(query, e.target.value);
    };

    // 7. Sự kiện màn hình Nhắc việc
    document.getElementById("btn-add-reminder").onclick = () => {
        document.getElementById("input-reminder-message").value = "";
        document.getElementById("input-reminder-time").value = "";
        document.getElementById("reminder-modal").classList.remove("hidden");
    };
    document.getElementById("btn-cancel-reminder").onclick = () => document.getElementById("reminder-modal").classList.add("hidden");
    document.getElementById("btn-save-reminder").onclick = saveReminder;

    document.getElementById("btn-morning-briefing").onclick = () => {
        // Chuyển sang màn hình chat và gửi lệnh /briefing
        document.querySelector('[data-screen="chat"]').click();
        const input = document.getElementById("user-input");
        input.value = "Hãy tạo cho tôi bản tin sáng hôm nay";
        sendUserMessage();
    };

    // 8. Sự kiện màn hình Nhật ký kiểm toán
    const btnRefreshAudit = document.getElementById("btn-refresh-audit");
    if (btnRefreshAudit) btnRefreshAudit.onclick = loadAuditLogs;

    // 9. Sự kiện màn hình Cài đặt & Chẩn đoán

    const btnSaveKey = document.getElementById("btn-save-key");
    if (btnSaveKey) btnSaveKey.onclick = saveGeminiKey;

    const btnToggleEye = document.getElementById("btn-toggle-key-visibility");
    if (btnToggleEye) {
        btnToggleEye.onclick = () => {
            const keyInp = document.getElementById("input-gemini-key");
            if (keyInp.type === "password") {
                keyInp.type = "text";
                btnToggleEye.innerText = "🔒";
            } else {
                keyInp.type = "password";
                btnToggleEye.innerText = "👁️";
            }
        };
    }

    const btnRefreshDiag = document.getElementById("btn-refresh-diagnostics");
    if (btnRefreshDiag) btnRefreshDiag.onclick = loadDiagnostics;

    const selectSettingsMode = document.getElementById("settings-select-mode");
    if (selectSettingsMode) {
        selectSettingsMode.onchange = async (e) => {
            try {
                await apiFetch("/api/settings/model", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: e.target.value }),
                });
                const chatModeSelect = document.getElementById("select-model-mode");
                if (chatModeSelect) chatModeSelect.value = e.target.value;
                loadDiagnostics();
            } catch (err) {
                alert("Lỗi đổi chế độ model: " + err.message);
            }
        };
    }

    const chkAutostart = document.getElementById("chk-autostart");
    if (chkAutostart) {
        chkAutostart.onchange = async (e) => {
            try {
                await apiFetch("/api/settings/autostart", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ enabled: e.target.checked }),
                });
                loadDiagnostics();
            } catch (err) {
                alert("Lỗi đổi cài đặt tự khởi động: " + err.message);
            }
        };
    }

    // 9. Tải trạng thái và nạp dữ liệu ban đầu
    try {
        const status = await apiFetch("/api/status");
        document.getElementById("ws-path-text").innerText = status.workspace_dir || "Workspace";
        document.getElementById("ws-path-text").title = status.workspace_dir || "";
    } catch (e) {
        console.warn("Chưa lấy được status ban đầu:", e);
    }

    loadConversations();
    connectWebSocket();
});
