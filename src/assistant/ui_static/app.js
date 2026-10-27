/**
 * Giao diện người dùng Trợ Lý AI trên Windows (Desktop Web UI).
 * Chạy 100% offline không phụ thuộc internet hay CDN bên ngoài.
 */

// =============================================================================
// CẤU HÌNH & QUẢN LÝ PHIÊN LÀM VIỆC (SESSION & STATE)
// =============================================================================

const urlParamToken = new URLSearchParams(window.location.search).get("token");
if (urlParamToken) {
    localStorage.setItem("troly_session_token", urlParamToken);
}

// =============================================================================
// CẤU HÌNH CÁ NHÂN HÓA & PROFILE (PERSONALIZATION & THEME)
// =============================================================================

const DEFAULT_PROFILE = {
    assistantName: "Bạn Đồng Hành",
    userName: "Bạn",
    assistantAvatar: "bot",
    userAvatar: "user",
    themeMode: "dark",
    accentColor: "#3b82f6",
};

const ACCENT_PRESETS = [
    { id: "ocean_blue", name: "Xanh Biển", hex: "#3b82f6", hover: "#2563eb", glow: "rgba(59, 130, 246, 0.28)", userBubbleDark: "#1e3a8a", userBubbleLight: "#1d4ed8" },
    { id: "emerald_green", name: "Ngọc Lục Bảo", hex: "#10b981", hover: "#059669", glow: "rgba(16, 185, 129, 0.28)", userBubbleDark: "#064e3b", userBubbleLight: "#047857" },
    { id: "royal_violet", name: "Tím Mộng Mơ", hex: "#8b5cf6", hover: "#7c3aed", glow: "rgba(139, 92, 246, 0.28)", userBubbleDark: "#4c1d95", userBubbleLight: "#6d28d9" },
    { id: "sunset_amber", name: "Hoàng Hôn", hex: "#f59e0b", hover: "#d97706", glow: "rgba(245, 158, 11, 0.28)", userBubbleDark: "#78350f", userBubbleLight: "#b45309" },
    { id: "sakura_pink", name: "Hoa Anh Đào", hex: "#ec4899", hover: "#db2777", glow: "rgba(236, 72, 153, 0.28)", userBubbleDark: "#831843", userBubbleLight: "#be185d" },
    { id: "crimson_red", name: "Đỏ Rực Rỡ", hex: "#ef4444", hover: "#dc2626", glow: "rgba(239, 68, 68, 0.28)", userBubbleDark: "#7f1d1d", userBubbleLight: "#b91c1c" },
    { id: "slate_modern", name: "Xám Tối Giản", hex: "#64748b", hover: "#475569", glow: "rgba(100, 116, 139, 0.28)", userBubbleDark: "#1e293b", userBubbleLight: "#334155" },
];

const QUICK_AVATARS_ASSISTANT = [
    { id: "bot", label: "Robot", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>` },
    { id: "sparkles", label: "Trợ lý AI", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
    { id: "terminal", label: "Chuyên viên", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>` },
    { id: "user", label: "Bạn đồng hành", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>` },
];

const QUICK_AVATARS_USER = [
    { id: "user", label: "Cá nhân", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>` },
    { id: "terminal", label: "Kỹ thuật", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>` },
    { id: "sparkles", label: "Sáng tạo", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
    { id: "bot", label: "Thành viên", icon: `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg>` },
];

function hexToRgb(hex) {
    let c = (hex || "#3b82f6").replace("#", "");
    if (c.length === 3) c = c.split("").map(x => x + x).join("");
    const num = parseInt(c, 16) || 0;
    return {
        r: (num >> 16) & 255,
        g: (num >> 8) & 255,
        b: num & 255,
    };
}

function loadProfileSettings() {
    try {
        const raw = localStorage.getItem("troly_profile_settings");
        if (raw) {
            const parsed = JSON.parse(raw);
            return {
                assistantName: (parsed.assistantName || DEFAULT_PROFILE.assistantName).trim(),
                userName: (parsed.userName || DEFAULT_PROFILE.userName).trim(),
                assistantAvatar: (parsed.assistantAvatar || DEFAULT_PROFILE.assistantAvatar).trim(),
                userAvatar: (parsed.userAvatar || DEFAULT_PROFILE.userAvatar).trim(),
                themeMode: (parsed.themeMode === "light" || parsed.themeMode === "dark") ? parsed.themeMode : DEFAULT_PROFILE.themeMode,
                accentColor: parsed.accentColor || DEFAULT_PROFILE.accentColor,
            };
        }
    } catch (e) {
        console.warn("Lỗi đọc profile từ localStorage:", e);
    }
    const legacyTheme = localStorage.getItem("troly_theme");
    return {
        ...DEFAULT_PROFILE,
        themeMode: legacyTheme === "light" ? "light" : "dark",
    };
}

const state = {
    token: urlParamToken || localStorage.getItem("troly_session_token") || "",
    currentConversationId: null,
    currentScreen: "chat",
    ws: null,
    isGenerating: false,
    currentAssistantRow: null,
    currentTextSpan: null,
    approvalTimerInterval: null,
    activeApprovalRequestId: null,
    profile: loadProfileSettings(),
    categories: [],
};

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

function renderAvatar(avatarStr, altText = "avatar") {
    const s = (avatarStr || "").trim();
    if (!s || s === "bot" || s === "🤖") {
        return `<span class="avatar-svg-wrap" title="${escapeHtml(altText)}"><svg class="icon-svg" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/></svg></span>`;
    }
    if (s === "user" || s === "🧑‍💻" || s === "👤") {
        return `<span class="avatar-svg-wrap" title="${escapeHtml(altText)}"><svg class="icon-svg" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></span>`;
    }
    if (s === "sparkles" || s === "🌟") {
        return `<span class="avatar-svg-wrap" title="${escapeHtml(altText)}"><svg class="icon-svg" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg></span>`;
    }
    if (s === "terminal" || s === "💻") {
        return `<span class="avatar-svg-wrap" title="${escapeHtml(altText)}"><svg class="icon-svg" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></span>`;
    }
    if (s.startsWith("http://") || s.startsWith("https://") || s.startsWith("data:image/")) {
        return `<img class="avatar-img" src="${escapeHtml(s)}" alt="${escapeHtml(altText)}" onerror="this.outerHTML='<span class=\\'avatar-svg-wrap\\'><svg class=\\'icon-svg\\' viewBox=\\'0 0 24 24\\'><rect x=\\'3\\' y=\\'11\\' width=\\'18\\' height=\\'10\\' rx=\\'2\\'/><circle cx=\\'12\\' cy=\\'5\\' r=\\'2\\'/><path d=\\'M12 7v4\\'/></svg></span>'"/>`;
    }
    return `<span class="avatar-emoji">${escapeHtml(s)}</span>`;
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
        const isAuthError = (
            event.code === 1008 ||
            event.code === 4003 ||
            (event.reason && (event.reason.toLowerCase().includes("token") || event.reason.toLowerCase().includes("forbidden")))
        );

        if (isAuthError) {
            console.warn("WebSocket bị từ chối kết nối do phiên làm việc hết hạn hoặc token không hợp lệ (mã: " + event.code + ")");
            // 1. Xóa ngay token cũ trong bộ nhớ
            localStorage.removeItem("troly_session_token");

            // 2. Nếu trên URL hiện tại có tham số ?token=..., cập nhật lại state.token từ URL
            const currentUrlToken = new URLSearchParams(window.location.search).get("token");
            if (currentUrlToken && currentUrlToken.trim().length >= 32) {
                state.token = currentUrlToken.trim();
                localStorage.setItem("troly_session_token", state.token);
                statusText.innerText = "Đang kết nối lại với token từ URL...";
                setTimeout(connectWebSocket, 1000);
                return;
            }

            // 3. Nếu trên URL không có token hợp lệ, hiển thị thông báo rõ ràng cho người dùng
            statusText.innerText = "Phiên làm việc hết hạn. Vui lòng mở lại từ phím tắt Desktop hoặc khay hệ thống.";
            if (typeof showToast === "function") {
                showToast("⚠️ Phiên làm việc đã hết hạn. Vui lòng mở lại ứng dụng từ phím tắt Desktop hoặc khay hệ thống để nhận Token bảo mật mới.", "error");
            }
            // Ngừng kết nối lại vô hạn để không làm ngập log máy chủ
            return;
        }

        statusText.innerText = "Mất kết nối (Đang thử lại...)";
        // Tự động kết nối lại sau 3 giây đối với các lỗi mạng tạm thời
        setTimeout(connectWebSocket, 3000);
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

const initWebSocket = connectWebSocket;

function handleServerEvent(type, data) {
    const chatContainer = document.getElementById("chat-messages");

    switch (type) {
        case "text_delta":
            if (state.currentTextSpan) {
                // Nếu trạng thái ban đầu là "..." từ phản hồi tức thời của server, thay thế bằng nội dung thực
                if (state.currentRawText === "..." && data.content !== "...") {
                    state.currentRawText = data.content;
                } else {
                    state.currentRawText = (state.currentRawText || "") + data.content;
                }

                // Tối ưu render: áp dụng requestAnimationFrame / throttle 40ms chống giật lag DOM
                const now = performance.now();
                if (!state.renderPending) {
                    if (now - (state.renderLastTime || 0) >= 40) {
                        state.renderLastTime = now;
                        state.currentTextSpan.innerHTML = parseMarkdown(state.currentRawText);
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    } else {
                        state.renderPending = true;
                        requestAnimationFrame(() => {
                            if (state.currentTextSpan) {
                                state.currentTextSpan.innerHTML = parseMarkdown(state.currentRawText);
                                chatContainer.scrollTop = chatContainer.scrollHeight;
                            }
                            state.renderLastTime = performance.now();
                            state.renderPending = false;
                        });
                    }
                }
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
                pill.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg> Đang chạy: <strong>${escapeHtml(data.tool_name)}</strong>...`;
                metaBox.appendChild(pill);
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            break;

        case "tool_result":
            const existingPill = document.getElementById(`tool-pill-${data.tool_name}`);
            if (existingPill) {
                if (data.is_error) {
                    existingPill.className = "meta-badge danger";
                    existingPill.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Lỗi: <strong>${escapeHtml(data.tool_name)}</strong>`;
                } else {
                    existingPill.className = "meta-badge";
                    existingPill.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg> Xong: <strong>${escapeHtml(data.tool_name)}</strong>`;
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

        case "focus_input":
            document.querySelector('[data-screen="chat"]')?.click();
            setTimeout(() => {
                const input = document.getElementById("user-input");
                if (input) input.focus();
            }, 60);
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
        user_name: state.profile.userName,
        assistant_name: state.profile.assistantName,
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
        <div class="message-avatar">${renderAvatar(state.profile.userAvatar, state.profile.userName)}</div>
        <div class="message-content-group">
            <div class="message-sender">${escapeHtml(state.profile.userName)}</div>
            <div class="message-bubble">
                <div class="message-text">${escapeHtml(text).replace(/\n/g, "<br>")}</div>
            </div>
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
        <div class="message-avatar">${renderAvatar(state.profile.assistantAvatar, state.profile.assistantName)}</div>
        <div class="message-content-group">
            <div class="message-sender">${escapeHtml(state.profile.assistantName)}</div>
            <div class="message-bubble">
                <div class="message-text typing-cursor"></div>
            </div>
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
    state.renderPending = false;
    document.getElementById("btn-send").classList.remove("hidden");
    document.getElementById("btn-cancel").classList.remove("hidden");
    document.getElementById("btn-cancel").classList.add("hidden");

    if (state.currentTextSpan) {
        state.currentTextSpan.classList.remove("typing-cursor");
        if (state.currentRawText) {
            state.currentTextSpan.innerHTML = parseMarkdown(state.currentRawText);
        } else {
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
        modelBadge.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg> ${escapeHtml(data.model_used)}`;
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
        <div class="message-avatar"><svg class="icon-svg" viewBox="0 0 24 24" style="color:var(--danger);"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg></div>
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
                    <div class="message-avatar">${renderAvatar(state.profile.assistantAvatar, state.profile.assistantName)}</div>
                    <div class="message-content-group">
                        <div class="message-sender">${escapeHtml(state.profile.assistantName)}</div>
                        <div class="message-bubble">
                            <div class="message-text">${parseMarkdown(m.content)}</div>
                            ${m.model_used ? `<div class="message-meta"><span class="meta-badge"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg> ${escapeHtml(m.model_used)}</span></div>` : ""}
                        </div>
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
// QUẢN LÝ DANH MỤC & TRÍ NHỚ DÀI HẠN (MEMORIES & CATEGORIES VIEW)
// =============================================================================

function getCategoryIconSvg(iconName) {
    const name = (iconName || "tag").toLowerCase();
    if (name === "heart") {
        return `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`;
    }
    if (name === "briefcase") {
        return `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>`;
    }
    if (name === "code") {
        return `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>`;
    }
    if (name === "info") {
        return `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    }
    return `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`;
}

async function loadCategories() {
    try {
        const cats = await apiFetch("/api/memories/categories");
        state.categories = cats || [];

        // 1. Cập nhật dropdown bộ lọc #filter-memory-category
        const filterSelect = document.getElementById("filter-memory-category");
        if (filterSelect) {
            const currentVal = filterSelect.value;
            filterSelect.innerHTML = '<option value="">Tất cả danh mục</option>';
            state.categories.forEach((cat) => {
                const opt = document.createElement("option");
                opt.value = cat.name;
                opt.innerText = `${cat.label} (${cat.name})`;
                if (cat.name === currentVal) opt.selected = true;
                filterSelect.appendChild(opt);
            });
        }

        // 2. Cập nhật dropdown chọn danh mục #input-memory-cat
        const inputSelect = document.getElementById("input-memory-cat");
        if (inputSelect) {
            const currentVal = inputSelect.value;
            inputSelect.innerHTML = "";
            state.categories.forEach((cat) => {
                const opt = document.createElement("option");
                opt.value = cat.name;
                opt.innerText = `${cat.label} (${cat.name})`;
                if (cat.name === currentVal) opt.selected = true;
                inputSelect.appendChild(opt);
            });
        }

        // 3. Render danh sách danh mục trong modal #category-table-body
        const tableBody = document.getElementById("category-table-body");
        if (tableBody) {
            tableBody.innerHTML = "";
            state.categories.forEach((cat) => {
                const tr = document.createElement("tr");
                const iconSvg = getCategoryIconSvg(cat.icon);
                const isGeneral = cat.name === "general";
                tr.innerHTML = `
                    <td>
                        <span class="cat-color-badge" style="background-color: ${cat.color}22; color: ${cat.color}; border: 1px solid ${cat.color}55;">
                            ${iconSvg}
                            <span class="cat-color-dot" style="background-color: ${cat.color};"></span>
                        </span>
                    </td>
                    <td><code>${escapeHtml(cat.name)}</code></td>
                    <td><strong>${escapeHtml(cat.label)}</strong></td>
                    <td style="text-align: right;">
                        <button class="btn btn-icon-sm btn-edit-category" data-id="${cat.id}" data-name="${cat.name}" data-label="${escapeHtml(cat.label)}" data-color="${cat.color}" title="Sửa nhãn danh mục">
                            <svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
                        </button>
                        ${isGeneral ? `<span style="font-size: 0.75rem; color: var(--text-muted); margin-left: 0.25rem;">(Mặc định)</span>` : `
                        <button class="btn btn-icon-sm btn-danger-hover btn-del-category" data-id="${cat.id}" data-name="${cat.name}" data-label="${escapeHtml(cat.label)}" title="Xóa danh mục">
                            <svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                        </button>
                        `}
                    </td>
                `;
                tableBody.appendChild(tr);
            });

            tableBody.querySelectorAll(".btn-edit-category").forEach((btn) => {
                btn.onclick = async () => {
                    const newLabel = prompt("Nhập tên hiển thị mới cho danh mục:", btn.dataset.label);
                    if (newLabel && newLabel.trim()) {
                        try {
                            await apiFetch(`/api/memories/categories/${btn.dataset.id}`, {
                                method: "PUT",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({ label: newLabel.trim() }),
                            });
                            showToast("Đã cập nhật danh mục thành công!", "success");
                            await loadCategories();
                            loadMemories();
                        } catch (err) {
                            alert("Lỗi sửa danh mục: " + err.message);
                        }
                    }
                };
            });

            tableBody.querySelectorAll(".btn-del-category").forEach((btn) => {
                btn.onclick = async () => {
                    const catName = btn.dataset.name;
                    const catLabel = btn.dataset.label;
                    if (confirm(`Bạn có chắc chắn muốn xoá danh mục "${catLabel}"? Mọi dữ kiện thuộc danh mục này sẽ tự động chuyển về "Chung" (general).`)) {
                        try {
                            await apiFetch(`/api/memories/categories/${btn.dataset.id}`, { method: "DELETE" });
                            showToast(`Đã xoá danh mục "${catLabel}"!`, "info");
                            await loadCategories();
                            loadMemories();
                        } catch (err) {
                            alert("Lỗi xoá danh mục: " + err.message);
                        }
                    }
                };
            });
        }
    } catch (e) {
        console.error("Không thể tải danh mục trí nhớ:", e);
    }
}

async function loadMemories(query = "", category = "") {
    try {
        if (!state.categories || state.categories.length === 0) {
            await loadCategories();
        }

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
            const catInfo = state.categories.find((c) => c.name === mem.category);
            const catLabel = catInfo ? catInfo.label : mem.category;
            const catColor = catInfo ? catInfo.color : "#3b82f6";
            const catIcon = catInfo ? getCategoryIconSvg(catInfo.icon) : getCategoryIconSvg("tag");

            card.innerHTML = `
                <div class="memory-card-header">
                    <span class="memory-cat-badge" style="background-color: ${catColor}22; color: ${catColor}; border: 1px solid ${catColor}55;">
                        ${catIcon}
                        <span>${escapeHtml(catLabel)}</span>
                    </span>
                </div>
                <div class="memory-card-body">${escapeHtml(mem.content)}</div>
                <div class="memory-card-footer">
                    <span>${new Date(mem.updated_at).toLocaleDateString("vi-VN")}</span>
                    <div>
                        <button class="btn btn-outline btn-sm btn-edit-mem" data-id="${mem.id}"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg> Sửa</button>
                        <button class="btn btn-outline btn-sm btn-del-mem" data-id="${mem.id}" style="color: var(--danger);"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Xoá</button>
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
            <span class="reminder-time"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ${dateStr}</span>
            <span class="meta-badge">${escapeHtml(rem.status)}</span>
        </div>
        <div class="reminder-message">${escapeHtml(rem.message)}</div>
        <div class="reminder-actions">
            <button class="btn btn-outline btn-sm btn-snooze-rem" data-id="${rem.id}"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Hoãn 10p</button>
            <button class="btn btn-outline btn-sm btn-del-rem" data-id="${rem.id}" style="color: var(--danger);"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Xoá</button>
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
            geminiEl.innerText = "Hoạt động tốt (Online)";
            geminiEl.className = "diag-value online";
        } else if (res.gemini_configured && !res.gemini_reachable) {
            geminiEl.innerText = "Đã có Key (Không có kết nối mạng)";
            geminiEl.className = "diag-value offline";
        } else {
            geminiEl.innerText = "Chưa cài đặt API Key";
            geminiEl.className = "diag-value error";
        }

        // 2. Nguồn API Key
        document.getElementById("diag-key-source").innerText = res.gemini_key_source || "Không";

        // 3. Trạng thái Ollama cục bộ
        const ollamaEl = document.getElementById("diag-ollama-status");
        if (res.ollama_running) {
            ollamaEl.innerText = "Đang chạy (Cổng 11434)";
            ollamaEl.className = "diag-value online";
        } else {
            ollamaEl.innerText = "Chưa bật (Cổng 11434)";
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

        // Cập nhật Gemini model dropdown
        const activeGemini = res.gemini_model || "gemini-1.5-flash";
        const geminiModelSelect = document.getElementById("settings-select-gemini-model");
        if (geminiModelSelect) {
            geminiModelSelect.innerHTML = "";
            const geminiCandidates = (res.gemini_models && res.gemini_models.length > 0)
                ? res.gemini_models
                : ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"];

            if (!geminiCandidates.includes(activeGemini)) {
                geminiCandidates.unshift(activeGemini);
            }

            geminiCandidates.forEach((m) => {
                const opt = document.createElement("option");
                opt.value = m;
                opt.innerText = m + (m === "gemini-1.5-flash" ? " (Khuyên dùng)" : "");
                if (m === activeGemini) {
                    opt.selected = true;
                }
                geminiModelSelect.appendChild(opt);
            });

            geminiModelSelect.onchange = async (e) => {
                await changeGeminiModel(e.target.value);
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

        // 5b. Hotkey checkbox
        const hotkeyCheck = document.getElementById("chk-hotkey");
        if (hotkeyCheck) {
            try {
                const hotkeyData = await apiFetch("/api/settings/hotkey");
                hotkeyCheck.checked = Boolean(hotkeyData.enabled);
            } catch (err) {
                console.debug("Chưa lấy được trạng thái hotkey:", err);
            }
        }

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

        // Tự động nạp danh sách Gemini API Keys đã lưu
        await loadGeminiKeys();
    } catch (err) {
        console.error("Lỗi tải chẩn đoán:", err);
    }
}

async function changeGeminiModel(newModel) {
    if (!newModel) return;
    try {
        const res = await apiFetch("/api/settings/gemini-model", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ gemini_model: newModel }),
        });
        if (res && res.ok) {
            await loadDiagnostics();
        }
    } catch (err) {
        console.error("Lỗi cập nhật model Gemini:", err);
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

// =============================================================================
// QUẢN LÝ GEMINI API KEYS (DYNAMIC ROWS, CRUD & TEST CONNECTIVITY)
// =============================================================================

let _geminiKeysCache = [];

async function loadGeminiKeys() {
    const container = document.getElementById("key-rows-container");
    const countBadge = document.getElementById("keys-count-badge");
    if (!container) return;

    try {
        const res = await apiFetch("/api/settings/gemini-keys");
        const keys = (res && Array.isArray(res.keys)) ? res.keys : [];
        _geminiKeysCache = keys;

        if (countBadge) {
            countBadge.innerText = `${keys.length} khóa`;
        }

        container.innerHTML = "";

        if (keys.length === 0) {
            container.innerHTML = `
                <div class="keys-empty-box">
                    <div class="keys-empty-icon"><svg class="icon-svg icon-lg" viewBox="0 0 24 24"><path d="m21 2-2 2m-1.5 1.5L14 9l-3 3-2 2-3 3a2.83 2.83 0 0 1-4-4l3-3 2-2 3.5-3.5L18.5 2z"/></svg></div>
                    <div class="keys-empty-title">Chưa có khóa Gemini API nào được lưu</div>
                    <div class="keys-empty-desc">
                        Hỗ trợ lưu nhiều API Key dự phòng trong Windows Credential Locker. Bấm nút bên dưới để thêm ô nhập khóa đầu tiên!
                    </div>
                    <button type="button" class="btn btn-primary btn-sm" id="btn-empty-add-key">
                        <svg class="icon-svg icon-sm" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg> Thêm Khóa Đầu Tiên
                    </button>
                </div>
            `;
            const emptyAddBtn = document.getElementById("btn-empty-add-key");
            if (emptyAddBtn) emptyAddBtn.onclick = addNewKeyRow;
            return;
        }

        keys.forEach((item) => {
            const rowEl = createKeyRowElement(item, false);
            container.appendChild(rowEl);
        });
    } catch (err) {
        console.error("Lỗi tải danh sách Gemini keys:", err);
        container.innerHTML = `<div class="key-test-feedback-box error">Lỗi tải danh sách khóa: ${escapeHtml(err.message)}</div>`;
    }
}

function addNewKeyRow() {
    const container = document.getElementById("key-rows-container");
    if (!container) return;

    // Xóa hộp trống nếu có
    const emptyBox = container.querySelector(".keys-empty-box");
    if (emptyBox) {
        emptyBox.remove();
    }

    const nextIndex = container.querySelectorAll(".key-row-card").length + 1;
    const dummyItem = {
        id: "",
        name: `Khóa ${nextIndex}`,
        masked_key: "",
        is_active: false,
    };

    const newRowEl = createKeyRowElement(dummyItem, true);
    container.appendChild(newRowEl);

    // Tự động cuộn đến và focus vào ô nhập khóa
    newRowEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const secretInput = newRowEl.querySelector(".input-key-secret");
    if (secretInput) {
        secretInput.focus();
    }
}

function createKeyRowElement(item, isNew = false) {
    const card = document.createElement("div");
    card.className = "key-row-card" + (item.is_active ? " active-key" : "") + (isNew ? " new-row" : "");
    if (item.id) card.dataset.keyId = item.id;

    const statusBadgeHtml = isNew
        ? `<span class="key-status-badge new">Mới (Chưa lưu)</span>`
        : (item.is_active
            ? `<span class="key-status-badge active"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Đang dùng</span>`
            : `<span class="key-status-badge standby">Dự phòng</span>`);

    const iconHtml = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="m21 2-2 2m-1.5 1.5L14 9l-3 3-2 2-3 3a2.83 2.83 0 0 1-4-4l3-3 2-2 3.5-3.5L18.5 2z"/></svg>`;

    card.innerHTML = `
        <div class="key-row-header">
            <div class="key-row-name-group">
                <span class="key-name-icon">${iconHtml}</span>
                <input 
                    type="text" 
                    class="input-key-name" 
                    value="${escapeHtml(item.name || '')}" 
                    placeholder="Tên gợi nhớ (VD: Khóa 1, Dự phòng...)"
                    title="Tên gợi nhớ của khóa"
                >
            </div>
            <div class="key-row-status">
                ${statusBadgeHtml}
            </div>
        </div>

        <div class="key-input-group">
            <div class="key-input-wrapper">
                <input 
                    type="password" 
                    class="input-key-secret" 
                    value="${isNew ? '' : escapeHtml(item.masked_key || '')}" 
                    data-masked="${isNew ? '' : escapeHtml(item.masked_key || '')}" 
                    placeholder="${isNew ? 'Dán Gemini API Key vào đây (AIzaSy...)' : 'Dán API key mới nếu muốn đổi...'}" 
                    autocomplete="off"
                    spellcheck="false"
                >
                <button type="button" class="btn-toggle-eye" title="Hiện / Ẩn khóa"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
            </div>
            <button type="button" class="btn-test-key" title="Kiểm tra kết nối khóa này với Google Gemini">
                <svg class="icon-svg icon-sm" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Kiểm Tra
            </button>
        </div>

        <div class="key-row-bottom">
            <div class="key-actions-left">
                <button type="button" class="btn-save-key-row">
                    <svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg> ${isNew ? 'Lưu Khóa' : 'Lưu Thay Đổi'}
                </button>
                ${!isNew && !item.is_active ? '<button type="button" class="btn-activate-key-row" title="Đặt khóa này làm khóa hoạt động chính"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Sử Dụng</button>' : ''}
                ${isNew ? '<button type="button" class="btn-cancel-key-row"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg> Hủy Bỏ</button>' : ''}
            </div>
            <div class="key-actions-right">
                ${!isNew ? '<button type="button" class="btn-delete-key-row" title="Xóa khóa này khỏi Windows"><svg class="icon-svg icon-sm" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg> Xóa</button>' : ''}
            </div>
        </div>

        <div class="key-test-feedback-box hidden"></div>
    `;

    // 1. Logic ẩn/hiện mật khẩu
    const secretInput = card.querySelector(".input-key-secret");
    const eyeBtn = card.querySelector(".btn-toggle-eye");
    eyeBtn.onclick = () => {
        if (secretInput.type === "password") {
            secretInput.type = "text";
            eyeBtn.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
            eyeBtn.title = "Ẩn khóa bí mật";
        } else {
            secretInput.type = "password";
            eyeBtn.innerHTML = `<svg class="icon-svg icon-sm" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
            eyeBtn.title = "Hiện khóa bí mật";
        }
    };

    // 2. Logic nút kiểm tra khóa
    const testBtn = card.querySelector(".btn-test-key");
    const feedbackBox = card.querySelector(".key-test-feedback-box");

    testBtn.onclick = async () => {
        const rawVal = secretInput.value.trim();
        const maskedVal = secretInput.dataset.masked || "";

        let testPayload = {};
        if (isNew) {
            if (!rawVal) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerText = "⚠️ Vui lòng dán Gemini API Key vào ô trước khi bấm Kiểm tra.";
                return;
            }
            if (rawVal.startsWith("...") || (rawVal.length < 30 && rawVal.includes("..."))) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerHTML = `⚠️ <strong>Bạn đang sao chép chữ bị che '...bM_Q'!</strong><br>Trên Google AI Studio, bạn hãy bấm vào <strong>nút 'Sao chép khóa'</strong> để lấy mã đầy đủ (bắt đầu bằng <code>AQ.</code> hoặc <code>AIzaSy...</code>).`;
                return;
            }
            if (!rawVal.includes("AIza") && !rawVal.includes("AQ.")) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerHTML = `⚠️ <strong>Khóa Gemini API không đúng định dạng!</strong><br>Khóa chuẩn từ Google AI Studio phải bắt đầu bằng <code>AQ.</code> (chuẩn mới) hoặc <code>AIzaSy...</code> (truyền thống). Vui lòng bấm vào nút <strong>Sao chép khóa</strong> trên Google AI Studio.`;
                return;
            }
            testPayload = { api_key: rawVal };
        } else {
            if (rawVal && rawVal !== maskedVal) {
                if (rawVal.startsWith("...") || (rawVal.length < 30 && rawVal.includes("..."))) {
                    feedbackBox.className = "key-test-feedback-box error";
                    feedbackBox.innerHTML = `⚠️ <strong>Bạn đang sao chép chữ bị che '...bM_Q'!</strong><br>Trên Google AI Studio, bạn hãy bấm vào <strong>nút 'Sao chép khóa'</strong> để lấy mã đầy đủ.`;
                    return;
                }
                testPayload = { api_key: rawVal };
            } else {
                testPayload = { key_id: item.id };
            }
        }

        const origBtnText = testBtn.innerHTML;
        testBtn.disabled = true;
        testBtn.innerHTML = `<span>⏳</span> Đang thử...`;
        feedbackBox.className = "key-test-feedback-box loading";
        feedbackBox.innerText = "Đang kết nối và kiểm tra sinh thử văn bản với Google Gemini...";

        try {
            const res = await apiFetch("/api/settings/gemini-keys/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(testPayload),
            });

            if (res && res.ok) {
                feedbackBox.className = "key-test-feedback-box success";
                feedbackBox.innerHTML = `${escapeHtml(res.message)}<br><small style="color:var(--text-secondary);display:inline-block;margin-top:5px;">Khóa đã hoạt động tốt! Hãy bấm nút <strong>${isNew ? 'Lưu Khóa' : 'Lưu Thay Đổi'}</strong> bên dưới để áp dụng.</small>`;
            } else {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerText = res?.message || res?.detail || "Khóa không hợp lệ hoặc lỗi mạng.";
            }
        } catch (err) {
            feedbackBox.className = "key-test-feedback-box error";
            feedbackBox.innerText = "Lỗi: " + err.message;
        } finally {
            testBtn.disabled = false;
            testBtn.innerHTML = origBtnText;
        }
    };

    // 3. Logic nút Lưu (Lưu khóa mới hoặc cập nhật khóa đã lưu)
    const saveBtn = card.querySelector(".btn-save-key-row");
    const nameInput = card.querySelector(".input-key-name");

    saveBtn.onclick = async () => {
        const nameVal = nameInput.value.trim();
        const secretVal = secretInput.value.trim();
        const maskedVal = secretInput.dataset.masked || "";

        if (isNew) {
            if (!secretVal) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerText = "Vui lòng dán khóa API vào ô trước khi lưu.";
                return;
            }
            if (secretVal.startsWith("...") || (secretVal.length < 30 && secretVal.includes("..."))) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerHTML = `<strong>Bạn đang sao chép chữ bị che '...bM_Q'!</strong><br>Trên Google AI Studio, bạn hãy bấm vào <strong>nút 'Sao chép khóa'</strong> để lấy mã đầy đủ.`;
                return;
            }
            if (!secretVal.includes("AIza") && !secretVal.includes("AQ.")) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerHTML = `<strong>Khóa Gemini API không đúng định dạng!</strong><br>Khóa chuẩn từ Google AI Studio phải bắt đầu bằng <code>AQ.</code> (chuẩn mới) hoặc <code>AIzaSy...</code> (truyền thống). Vui lòng bấm vào nút <strong>Sao chép khóa</strong> trên Google AI Studio.`;
                return;
            }

            const origSaveText = saveBtn.innerHTML;
            saveBtn.disabled = true;
            saveBtn.innerHTML = `Đang lưu...`;

            try {
                const res = await apiFetch("/api/settings/gemini-keys", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ api_key: secretVal, name: nameVal }),
                });

                if (res && res.ok) {
                    if (res.key_id) {
                        try {
                            await apiFetch(`/api/settings/gemini-keys/${encodeURIComponent(res.key_id)}/active`, { method: "POST" });
                        } catch (e) {
                            console.warn("Lỗi auto active key:", e);
                        }
                    }
                    showToast("Đã lưu và kích hoạt khóa chính thành công!", "success");
                    await loadGeminiKeys();
                    await loadDiagnostics();
                } else {
                    feedbackBox.className = "key-test-feedback-box error";
                    feedbackBox.innerText = res?.detail || "Không thể lưu khóa.";
                }
            } catch (err) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerText = "Lỗi: " + err.message;
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = origSaveText;
            }
        } else {
            const hasNewSecret = secretVal && secretVal !== maskedVal && !secretVal.includes("...");
            const hasNewName = nameVal && nameVal !== item.name;

            if (!hasNewSecret && !hasNewName) {
                showToast("Không có thay đổi nào cần lưu.", "info");
                return;
            }

            const origSaveText = saveBtn.innerHTML;
            saveBtn.disabled = true;
            saveBtn.innerHTML = `Đang cập nhật...`;

            try {
                const updatePayload = {
                    name: nameVal || item.name,
                };
                if (hasNewSecret) {
                    updatePayload.api_key = secretVal;
                }

                const res = await apiFetch(`/api/settings/gemini-keys/${encodeURIComponent(item.id)}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(updatePayload),
                });

                if (res && res.ok) {
                    try {
                        await apiFetch(`/api/settings/gemini-keys/${encodeURIComponent(item.id)}/active`, { method: "POST" });
                    } catch (e) {
                        console.warn("Lỗi auto active key:", e);
                    }
                    showToast("Đã cập nhật và kích hoạt khóa chính thành công!", "success");
                    await loadGeminiKeys();
                    await loadDiagnostics();
                } else {
                    feedbackBox.className = "key-test-feedback-box error";
                    feedbackBox.innerText = res?.detail || "Không thể cập nhật khóa.";
                }
            } catch (err) {
                feedbackBox.className = "key-test-feedback-box error";
                feedbackBox.innerText = "Lỗi: " + err.message;
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = origSaveText;
            }
        }
    };

    // 4. Logic nút Kích hoạt / Sử dụng (cho khóa dự phòng)
    const activateBtn = card.querySelector(".btn-activate-key-row");
    if (activateBtn) {
        activateBtn.onclick = async () => {
            try {
                const res = await apiFetch(`/api/settings/gemini-keys/${encodeURIComponent(item.id)}/active`, {
                    method: "POST",
                });
                if (res && res.ok) {
                    showToast(`Đã chuyển sang sử dụng "${item.name}"!`, "success");
                    await loadGeminiKeys();
                    await loadDiagnostics();
                } else {
                    alert("Lỗi: " + (res?.detail || "Không thể kích hoạt khóa."));
                }
            } catch (err) {
                alert("Lỗi: " + err.message);
            }
        };
    }

    // 5. Logic nút Xóa khóa
    const deleteBtn = card.querySelector(".btn-delete-key-row");
    if (deleteBtn) {
        deleteBtn.onclick = async () => {
            const confirmed = confirm(`Bạn có chắc chắn muốn xóa khóa "${item.name}" khỏi Windows Credential Locker?`);
            if (!confirmed) return;

            try {
                const res = await apiFetch(`/api/settings/gemini-keys/${encodeURIComponent(item.id)}`, {
                    method: "DELETE",
                });
                if (res && res.ok) {
                    showToast(`Đã xóa khóa "${item.name}"`, "info");
                    await loadGeminiKeys();
                    await loadDiagnostics();
                } else {
                    alert("Lỗi: " + (res?.detail || "Không thể xóa khóa."));
                }
            } catch (err) {
                alert("Lỗi: " + err.message);
            }
        };
    }

    // 6. Logic nút Hủy (cho ô thêm mới chưa lưu)
    const cancelBtn = card.querySelector(".btn-cancel-key-row");
    if (cancelBtn) {
        cancelBtn.onclick = () => {
            card.remove();
            const container = document.getElementById("key-rows-container");
            if (container && container.querySelectorAll(".key-row-card").length === 0) {
                loadGeminiKeys();
            }
        };
    }

    return card;
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
// THÔNG BÁO TOAST & KÉO-THẢ TẬP TIN (DRAG & DROP / FILE UPLOAD)
// =============================================================================

function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        container.style.cssText = "position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;pointer-events:none;";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    const bg = type === "error" ? "var(--danger, #ef4444)" : type === "success" ? "var(--success, #10b981)" : "var(--accent, #3b82f6)";
    toast.style.cssText = `background:${bg};color:#ffffff;padding:0.6rem 1.1rem;border-radius:8px;font-size:0.88rem;box-shadow:0 4px 14px rgba(0,0,0,0.3);transition:all 0.25s ease;pointer-events:auto;max-width:380px;word-break:break-word;display:flex;align-items:center;gap:0.5rem;`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateY(8px)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

async function uploadFileToWorkspace(file) {
    if (!file) return;
    const maxBytes = 25 * 1024 * 1024;
    if (file.size > maxBytes) {
        showToast("Dung lượng tệp vượt quá 25MB: " + file.name, "error");
        return;
    }

    showToast(`Đang tải tệp "${file.name}" lên Workspace...`, "info");
    const formData = new FormData();
    formData.append("file", file);

    try {
        const token = state.token || localStorage.getItem("troly_session_token") || "";
        const url = `/api/upload-file?token=${encodeURIComponent(token)}`;
        const resp = await fetch(url, {
            method: "POST",
            headers: {
                "X-Session-Token": token,
            },
            body: formData,
        });

        if (!resp.ok) {
            const errJson = await resp.json().catch(() => ({}));
            throw new Error(errJson.detail || "Không thể tải lên tệp.");
        }

        const data = await resp.json();
        showToast(`Đã tải lên "${data.filename}" thành công!`, "success");

        // Chuyển sang màn hình chat và tự động điền câu lệnh vào khung chat
        document.querySelector('[data-screen="chat"]')?.click();
        const textarea = document.getElementById("user-input");
        if (textarea) {
            textarea.value = `Hãy tóm tắt và phân tích nội dung file: ${data.filename}`;
            textarea.style.height = "auto";
            textarea.style.height = Math.min(textarea.scrollHeight, 180) + "px";
            textarea.focus();
        }
    } catch (err) {
        showToast("Lỗi tải tệp: " + err.message, "error");
    }
}

function initDragAndDrop() {
    const dropzone = document.getElementById("dropzone-overlay");
    let dragCounter = 0;

    window.addEventListener("dragenter", (e) => {
        if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
            e.preventDefault();
            dragCounter++;
            if (dropzone) dropzone.classList.remove("hidden");
        }
    });

    window.addEventListener("dragover", (e) => {
        if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
            e.preventDefault();
            e.dataTransfer.dropEffect = "copy";
        }
    });

    window.addEventListener("dragleave", (e) => {
        if (e.dataTransfer && e.dataTransfer.types && Array.from(e.dataTransfer.types).includes("Files")) {
            e.preventDefault();
            dragCounter--;
            if (dragCounter <= 0) {
                dragCounter = 0;
                if (dropzone) dropzone.classList.add("hidden");
            }
        }
    });

    window.addEventListener("drop", async (e) => {
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            e.preventDefault();
            dragCounter = 0;
            if (dropzone) dropzone.classList.add("hidden");

            const files = Array.from(e.dataTransfer.files);
            for (const file of files) {
                await uploadFileToWorkspace(file);
            }
        }
    });
}

// =============================================================================
// QUẢN LÝ CÁ NHÂN HÓA & GIAO DIỆN (PERSONALIZATION & ACCENTS)
// =============================================================================

function renderWelcomeMessage() {
    const chatContainer = document.getElementById("chat-messages");
    if (!chatContainer) return;
    const p = state.profile || DEFAULT_PROFILE;
    chatContainer.innerHTML = `
        <div class="message-row assistant">
            <div class="message-avatar">${renderAvatar(p.assistantAvatar, p.assistantName)}</div>
            <div class="message-content-group">
                <div class="message-sender">${escapeHtml(p.assistantName)}</div>
                <div class="message-bubble">
                    <div class="message-text">
                        Xin chào <strong>${escapeHtml(p.userName)}</strong>! Tôi là <strong>${escapeHtml(p.assistantName)}</strong> trên Windows. Tôi có thể giúp bạn:
                        <ul>
                            <li><strong>Quản lý file & thư mục:</strong> tạo, đọc, sửa, sắp xếp thông minh.</li>
                            <li><strong>Tài liệu văn phòng:</strong> đọc/tạo PDF, Word (.docx), Excel (.xlsx).</li>
                            <li><strong>Tra cứu web:</strong> tổng hợp thông tin với chế độ bảo mật chống SSRF.</li>
                            <li><strong>Nhắc việc đúng giờ:</strong> báo thức, hoãn nhắc và phát thông báo Windows Toast.</li>
                            <li><strong>Ghi nhớ dữ kiện:</strong> sở thích, quy tắc đặt tên, dự án của bạn qua các phiên.</li>
                        </ul>
                        Hãy nhập câu hỏi hoặc yêu cầu bằng tiếng Việt bên dưới để bắt đầu!
                    </div>
                </div>
            </div>
        </div>
    `;
}

function applyThemeSettings(profile = state.profile) {
    if (!profile) return;
    const isLight = profile.themeMode === "light";
    document.body.className = isLight ? "light-theme" : "dark-theme";
    document.documentElement.className = isLight ? "light-theme" : "dark-theme";

    // Cập nhật icon theme ở sidebar footer
    const themeIcon = document.getElementById("theme-icon");
    if (themeIcon) {
        themeIcon.innerHTML = isLight
            ? `<svg class="icon-svg" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`
            : `<svg class="icon-svg" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
    }

    // Tính toán dải màu CSS :root & body
    const preset = ACCENT_PRESETS.find((pr) => pr.hex.toLowerCase() === (profile.accentColor || "").toLowerCase());
    const rgb = hexToRgb(profile.accentColor || "#3b82f6");
    const hoverColor = preset ? preset.hover : `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.85)`;
    const glowColor = preset ? preset.glow : `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.28)`;
    const userBubbleColor = isLight
        ? (preset ? preset.userBubbleLight : profile.accentColor)
        : (preset ? preset.userBubbleDark : profile.accentColor);

    const root = document.documentElement;
    root.style.setProperty("--accent", profile.accentColor);
    root.style.setProperty("--accent-hover", hoverColor);
    root.style.setProperty("--accent-glow", glowColor);
    root.style.setProperty("--user-bubble", userBubbleColor);

    document.body.style.setProperty("--accent", profile.accentColor);
    document.body.style.setProperty("--accent-hover", hoverColor);
    document.body.style.setProperty("--accent-glow", glowColor);
    document.body.style.setProperty("--user-bubble", userBubbleColor);

    // Cập nhật thương hiệu sidebar
    const brandAvatar = document.getElementById("brand-avatar");
    if (brandAvatar) {
        brandAvatar.innerHTML = renderAvatar(profile.assistantAvatar, profile.assistantName);
    }
    const brandName = document.getElementById("brand-name");
    if (brandName) {
        brandName.innerText = profile.assistantName;
    }

    // Đồng bộ trạng thái trên màn hình Cá nhân hóa & Giao diện
    syncPersonalizationControls(profile);
}

function saveProfileSettings(newProfile) {
    state.profile = {
        assistantName: (newProfile.assistantName || DEFAULT_PROFILE.assistantName).trim(),
        userName: (newProfile.userName || DEFAULT_PROFILE.userName).trim(),
        assistantAvatar: (newProfile.assistantAvatar || DEFAULT_PROFILE.assistantAvatar).trim(),
        userAvatar: (newProfile.userAvatar || DEFAULT_PROFILE.userAvatar).trim(),
        themeMode: (newProfile.themeMode === "light" || newProfile.themeMode === "dark") ? newProfile.themeMode : "dark",
        accentColor: newProfile.accentColor || DEFAULT_PROFILE.accentColor,
    };
    try {
        localStorage.setItem("troly_profile_settings", JSON.stringify(state.profile));
        localStorage.setItem("troly_theme", state.profile.themeMode);
    } catch (e) {
        console.error("Lỗi ghi cấu hình cá nhân hóa:", e);
    }
    applyThemeSettings(state.profile);
}

function syncPersonalizationControls(profile = state.profile) {
    const inputAstName = document.getElementById("input-assistant-name");
    if (inputAstName && document.activeElement !== inputAstName) {
        inputAstName.value = profile.assistantName;
    }
    const inputUserName = document.getElementById("input-user-name");
    if (inputUserName && document.activeElement !== inputUserName) {
        inputUserName.value = profile.userName;
    }
    const inputAstAvatar = document.getElementById("input-assistant-avatar");
    if (inputAstAvatar && document.activeElement !== inputAstAvatar) {
        inputAstAvatar.value = profile.assistantAvatar;
    }
    const inputUserAvatar = document.getElementById("input-user-avatar");
    if (inputUserAvatar && document.activeElement !== inputUserAvatar) {
        inputUserAvatar.value = profile.userAvatar;
    }

    const prevAst = document.getElementById("preview-assistant-avatar");
    if (prevAst) {
        prevAst.innerHTML = renderAvatar(profile.assistantAvatar, profile.assistantName);
    }
    const prevUser = document.getElementById("preview-user-avatar");
    if (prevUser) {
        prevUser.innerHTML = renderAvatar(profile.userAvatar, profile.userName);
    }

    const colorPicker = document.getElementById("input-custom-accent");
    if (colorPicker && document.activeElement !== colorPicker) {
        colorPicker.value = profile.accentColor;
    }
    const hexText = document.getElementById("custom-accent-hex");
    if (hexText) {
        hexText.innerText = profile.accentColor;
    }

    // Active state swatches
    document.querySelectorAll(".accent-swatch-item").forEach((item) => {
        const itemHex = item.dataset.hex;
        if (itemHex && itemHex.toLowerCase() === (profile.accentColor || "").toLowerCase()) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    // Theme mode pills
    const pillDark = document.getElementById("pill-theme-dark");
    const pillLight = document.getElementById("pill-theme-light");
    if (pillDark && pillLight) {
        if (profile.themeMode === "light") {
            pillLight.classList.add("active");
            pillDark.classList.remove("active");
            const r = pillLight.querySelector("input");
            if (r) r.checked = true;
        } else {
            pillDark.classList.add("active");
            pillLight.classList.remove("active");
            const r = pillDark.querySelector("input");
            if (r) r.checked = true;
        }
    }
}

function initPersonalizationUI() {
    // 1. Render danh sách avatar chọn nhanh cho Trợ lý
    const astEmojiContainer = document.getElementById("quick-emojis-assistant");
    if (astEmojiContainer && astEmojiContainer.children.length === 0) {
        QUICK_AVATARS_ASSISTANT.forEach((av) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "emoji-quick-btn";
            btn.innerHTML = `${av.icon} <span class="quick-avatar-label">${escapeHtml(av.label)}</span>`;
            btn.title = `Chọn đại diện ${av.label}`;
            btn.onclick = () => {
                const inp = document.getElementById("input-assistant-avatar");
                if (inp) inp.value = av.id;
                const prev = document.getElementById("preview-assistant-avatar");
                if (prev) prev.innerHTML = renderAvatar(av.id);
            };
            astEmojiContainer.appendChild(btn);
        });
    }

    // 2. Render danh sách avatar chọn nhanh cho Người dùng
    const userEmojiContainer = document.getElementById("quick-emojis-user");
    if (userEmojiContainer && userEmojiContainer.children.length === 0) {
        QUICK_AVATARS_USER.forEach((av) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "emoji-quick-btn";
            btn.innerHTML = `${av.icon} <span class="quick-avatar-label">${escapeHtml(av.label)}</span>`;
            btn.title = `Chọn đại diện ${av.label}`;
            btn.onclick = () => {
                const inp = document.getElementById("input-user-avatar");
                if (inp) inp.value = av.id;
                const prev = document.getElementById("preview-user-avatar");
                if (prev) prev.innerHTML = renderAvatar(av.id);
            };
            userEmojiContainer.appendChild(btn);
        });
    }

    // 3. Render 7 Preset Accent Color Swatches
    const swatchContainer = document.getElementById("accent-swatches-container");
    if (swatchContainer && swatchContainer.children.length === 0) {
        ACCENT_PRESETS.forEach((preset) => {
            const item = document.createElement("div");
            item.className = "accent-swatch-item";
            item.dataset.hex = preset.hex;
            if (preset.hex.toLowerCase() === (state.profile.accentColor || "").toLowerCase()) {
                item.classList.add("active");
            }
            item.innerHTML = `
                <span class="swatch-circle" style="background-color: ${preset.hex};"></span>
                <span class="swatch-title">${escapeHtml(preset.name)}</span>
            `;
            item.onclick = () => {
                state.profile.accentColor = preset.hex;
                applyThemeSettings(state.profile);
            };
            swatchContainer.appendChild(item);
        });
    }

    // 4. Color Picker tùy biến
    const colorPicker = document.getElementById("input-custom-accent");
    if (colorPicker) {
        colorPicker.oninput = (e) => {
            const hex = e.target.value;
            state.profile.accentColor = hex;
            const hexText = document.getElementById("custom-accent-hex");
            if (hexText) hexText.innerText = hex;
            applyThemeSettings(state.profile);
        };
    }

    // 5. Thay đổi trực tiếp khi gõ avatar
    const inputAstAvatar = document.getElementById("input-assistant-avatar");
    if (inputAstAvatar) {
        inputAstAvatar.oninput = (e) => {
            const prev = document.getElementById("preview-assistant-avatar");
            if (prev) prev.innerHTML = renderAvatar(e.target.value);
        };
    }
    const inputUserAvatar = document.getElementById("input-user-avatar");
    if (inputUserAvatar) {
        inputUserAvatar.oninput = (e) => {
            const prev = document.getElementById("preview-user-avatar");
            if (prev) prev.innerHTML = renderAvatar(e.target.value);
        };
    }

    // 6. Theme Mode Pills
    const pillDark = document.getElementById("pill-theme-dark");
    if (pillDark) {
        pillDark.onclick = () => {
            state.profile.themeMode = "dark";
            applyThemeSettings(state.profile);
        };
    }
    const pillLight = document.getElementById("pill-theme-light");
    if (pillLight) {
        pillLight.onclick = () => {
            state.profile.themeMode = "light";
            applyThemeSettings(state.profile);
        };
    }

    // 7. Nút Lưu cài đặt giao diện
    const btnSave = document.getElementById("btn-save-profile");
    if (btnSave) {
        btnSave.onclick = () => {
            const astName = (document.getElementById("input-assistant-name")?.value || "").trim() || DEFAULT_PROFILE.assistantName;
            const userName = (document.getElementById("input-user-name")?.value || "").trim() || DEFAULT_PROFILE.userName;
            const astAvatar = (document.getElementById("input-assistant-avatar")?.value || "").trim() || DEFAULT_PROFILE.assistantAvatar;
            const userAvatar = (document.getElementById("input-user-avatar")?.value || "").trim() || DEFAULT_PROFILE.userAvatar;
            const accent = state.profile.accentColor || DEFAULT_PROFILE.accentColor;
            const theme = state.profile.themeMode || DEFAULT_PROFILE.themeMode;

            saveProfileSettings({
                assistantName: astName,
                userName: userName,
                assistantAvatar: astAvatar,
                userAvatar: userAvatar,
                themeMode: theme,
                accentColor: accent,
            });

            if (typeof showToast === "function") {
                showToast("Đã lưu cài đặt giao diện và hồ sơ cá nhân!", "success");
            } else {
                alert("Đã lưu cài đặt giao diện và hồ sơ cá nhân!");
            }
        };
    }

    // 8. Nút Khôi phục mặc định
    const btnReset = document.getElementById("btn-reset-profile");
    if (btnReset) {
        btnReset.onclick = () => {
            if (confirm("Bạn có chắc chắn muốn khôi phục giao diện và danh xưng về mặc định ban đầu không?")) {
                saveProfileSettings(DEFAULT_PROFILE);
                if (typeof showToast === "function") {
                    showToast("Đã khôi phục cài đặt mặc định!", "info");
                }
            }
        };
    }

    syncPersonalizationControls(state.profile);
}

// =============================================================================
// KHỞI TẠO VÀ LẮNG NGHE SỰ KIỆN (INITIALIZATION)
// =============================================================================

document.addEventListener("DOMContentLoaded", async () => {
    await initI18n();

    // Khởi tạo và nạp Theme & Profile ngay lập tức
    applyThemeSettings(state.profile);
    initPersonalizationUI();
    renderWelcomeMessage();

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

            if (state.currentScreen === "memories") {
                loadCategories().then(() => loadMemories());
            }
            if (state.currentScreen === "reminders") loadReminders();
            if (state.currentScreen === "audit") loadAuditLogs();
            if (state.currentScreen === "appearance") syncPersonalizationControls(state.profile);
            if (state.currentScreen === "settings") {
                loadDiagnostics();
                loadGeminiKeys();
            }
        };
    });

    // 2. Chuyển đổi Dark/Light mode ở sidebar footer
    const themeBtn = document.getElementById("theme-toggle");
    if (themeBtn) {
        themeBtn.onclick = () => {
            const newTheme = document.body.classList.contains("dark-theme") ? "light" : "dark";
            state.profile.themeMode = newTheme;
            saveProfileSettings(state.profile);
        };
    }

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
        renderWelcomeMessage();
    };

    document.getElementById("select-conversations").onchange = (e) => {
        if (e.target.value) {
            state.currentConversationId = e.target.value;
            loadConversationMessages(state.currentConversationId);
        }
    };

    // 5.1. Đổi tên cuộc trò chuyện
    const btnRenameConv = document.getElementById("btn-rename-conv");
    if (btnRenameConv) {
        btnRenameConv.onclick = async () => {
            if (!state.currentConversationId) {
                showToast("Vui lòng chọn hoặc bắt đầu cuộc trò chuyện trước.", "warning");
                return;
            }
            const select = document.getElementById("select-conversations");
            const currentTitle = select.options[select.selectedIndex]?.text || "Cuộc trò chuyện";
            const newTitle = prompt("Nhập tiêu đề mới cho cuộc trò chuyện:", currentTitle);
            if (newTitle && newTitle.trim()) {
                try {
                    await apiFetch(`/api/conversations/${state.currentConversationId}`, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ title: newTitle.trim() }),
                    });
                    showToast("Đã đổi tên cuộc trò chuyện thành công!", "success");
                    await loadConversations();
                } catch (err) {
                    alert("Lỗi đổi tên cuộc trò chuyện: " + err.message);
                }
            }
        };
    }

    // 5.2. Lưu dữ kiện cuộc trò chuyện vào trí nhớ dài hạn
    const btnSaveConvMem = document.getElementById("btn-save-conv-memory");
    if (btnSaveConvMem) {
        btnSaveConvMem.onclick = async () => {
            if (!state.currentConversationId) {
                showToast("Vui lòng chọn cuộc trò chuyện cần lưu trí nhớ.", "warning");
                return;
            }
            const origHtml = btnSaveConvMem.innerHTML;
            btnSaveConvMem.innerHTML = `<span class="loading-spinner" style="width:14px;height:14px;border-width:2px;display:inline-block;"></span>`;
            btnSaveConvMem.disabled = true;
            try {
                const res = await apiFetch(`/api/conversations/${state.currentConversationId}/save-to-memory`, {
                    method: "POST",
                });
                if (res.count > 0) {
                    showToast(`Đã trích xuất và lưu ${res.count} dữ kiện vào Trí nhớ dài hạn!`, "success");
                    if (state.currentScreen === "memories") loadMemories();
                } else {
                    showToast("Cuộc trò chuyện chưa có thông tin dữ kiện mới để lưu.", "info");
                }
            } catch (err) {
                showToast("Lỗi trích xuất trí nhớ: " + err.message, "error");
            } finally {
                btnSaveConvMem.innerHTML = origHtml;
                btnSaveConvMem.disabled = false;
            }
        };
    }

    // 5.3. Xóa cuộc trò chuyện
    const btnDelConv = document.getElementById("btn-delete-conv");
    if (btnDelConv) {
        btnDelConv.onclick = async () => {
            if (!state.currentConversationId) {
                showToast("Vui lòng chọn cuộc trò chuyện cần xóa.", "warning");
                return;
            }
            if (confirm("Bạn có chắc chắn muốn xóa toàn bộ cuộc trò chuyện này không?")) {
                try {
                    await apiFetch(`/api/conversations/${state.currentConversationId}`, { method: "DELETE" });
                    showToast("Đã xóa cuộc trò chuyện thành công!", "info");
                    state.currentConversationId = null;
                    document.getElementById("select-conversations").value = "";
                    renderWelcomeMessage();
                    await loadConversations();
                } catch (err) {
                    alert("Lỗi xóa cuộc trò chuyện: " + err.message);
                }
            }
        };
    }

    // 6. Quản lý danh mục trí nhớ
    const btnManageCats = document.getElementById("btn-manage-categories");
    const catModal = document.getElementById("category-modal");
    if (btnManageCats && catModal) {
        btnManageCats.onclick = () => {
            loadCategories();
            catModal.classList.remove("hidden");
        };
    }
    const btnCloseCatModal = document.getElementById("btn-close-category-modal");
    if (btnCloseCatModal && catModal) {
        btnCloseCatModal.onclick = () => catModal.classList.add("hidden");
    }
    const btnDoneCats = document.getElementById("btn-done-categories");
    if (btnDoneCats && catModal) {
        btnDoneCats.onclick = () => catModal.classList.add("hidden");
    }

    const inputCatColor = document.getElementById("input-cat-color");
    if (inputCatColor) {
        inputCatColor.oninput = (e) => {
            const hexText = document.getElementById("cat-color-hex");
            if (hexText) hexText.innerText = e.target.value;
        };
    }

    const btnSubmitCat = document.getElementById("btn-submit-category");
    if (btnSubmitCat) {
        btnSubmitCat.onclick = async () => {
            const name = (document.getElementById("input-cat-name")?.value || "").trim();
            const label = (document.getElementById("input-cat-label")?.value || "").trim();
            const color = document.getElementById("input-cat-color")?.value || "#3b82f6";
            if (!name || !label) {
                alert("Vui lòng nhập cả mã danh mục và nhãn hiển thị.");
                return;
            }
            try {
                await apiFetch("/api/memories/categories", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, label, color, icon: "tag" }),
                });
                showToast(`Đã thêm danh mục "${label}"!`, "success");
                document.getElementById("input-cat-name").value = "";
                document.getElementById("input-cat-label").value = "";
                await loadCategories();
                loadMemories();
            } catch (err) {
                alert("Lỗi thêm danh mục: " + err.message);
            }
        };
    }

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
    const btnAddKeyTop = document.getElementById("btn-add-key-top");
    if (btnAddKeyTop) btnAddKeyTop.onclick = addNewKeyRow;

    const btnAddKeyRow = document.getElementById("btn-add-key-row");
    if (btnAddKeyRow) btnAddKeyRow.onclick = addNewKeyRow;

    const btnRefreshKeys = document.getElementById("btn-refresh-keys");
    if (btnRefreshKeys) btnRefreshKeys.onclick = loadGeminiKeys;

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

    const chkHotkey = document.getElementById("chk-hotkey");
    if (chkHotkey) {
        chkHotkey.onchange = async (e) => {
            try {
                await apiFetch("/api/settings/hotkey", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ enabled: e.target.checked }),
                });
                showToast(e.target.checked ? "Đã bật phím tắt Ctrl+Shift+Space" : "Đã tắt phím tắt toàn cục", "info");
                loadDiagnostics();
            } catch (err) {
                alert("Lỗi đổi cài đặt phím tắt: " + err.message);
            }
        };
    }

    // Tự động focus ô chat khi cửa sổ Trợ lý được kích hoạt (Spotlight Mode)
    window.addEventListener("focus", () => {
        if (state.currentScreen === "chat") {
            const input = document.getElementById("user-input");
            if (input) input.focus();
        }
    });

    // Kích hoạt tính năng kéo-thả tệp tin
    initDragAndDrop();

    // 9. Tải trạng thái và nạp dữ liệu ban đầu
    try {
        const status = await apiFetch("/api/status");
        document.getElementById("ws-path-text").innerText = status.workspace_dir || "Workspace";
        document.getElementById("ws-path-text").title = status.workspace_dir || "";
    } catch (e) {
        console.warn("Chưa lấy được status ban đầu:", e);
    }

    await loadCategories();
    loadConversations();
    loadGeminiKeys();
    connectWebSocket();
});
