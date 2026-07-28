/**
 * Delphic AI - Client-side JavaScript
 */

const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const clearBtn = document.getElementById("clearBtn");
const themeToggle = document.getElementById("themeToggle");
const themeMenu = document.getElementById("themeMenu");
const themeOptions = document.querySelectorAll("[data-theme-choice]");
const themePicker = themeToggle.closest(".theme-picker");
const menuBtn = document.getElementById("menuBtn");
const sidebar = document.getElementById("sidebar");
const tokenCount = document.getElementById("tokenCount");
const downloadChatBtn = document.getElementById("downloadChatBtn");
const stepByStepToggle = document.getElementById("stepByStepToggle");
const stepModeNote = document.getElementById("stepModeNote");
const quizModeBtn = document.getElementById("quizModeBtn");
const aiSettingsBtn = document.getElementById("aiSettingsBtn");
const startTutorButtons = document.querySelectorAll("[data-start-tutor]");
const startScienceButtons = document.querySelectorAll("[data-start-science]");
const homePromptButtons = document.querySelectorAll("[data-home-prompt]");
const tutorMode = document.body.dataset.tutorMode || "math";
const apiBase = document.body.dataset.apiBase || "";
const graphingEnabled = document.body.dataset.graphingEnabled !== "false";
const practicePrompt = document.body.dataset.practicePrompt || "Give me a similar practice problem.";
const practiceButtonLabel = document.body.dataset.practiceButtonLabel || "Practice Similar Problem";
const quizPrompt = document.body.dataset.quizPrompt || "Start a 5-question science quiz.";
const quizButtonLabel = document.body.dataset.quizButtonLabel || "Quiz Mode";
const downloadButtonLabel = document.body.dataset.downloadButtonLabel || "Download Chat";
const isScienceMode = tutorMode === "science";
let isSending = false;
let aiSettingsStatus = { configured: false, provider: "groq", providers: [] };

function apiUrl(path) {
    return `${apiBase}${path}`;
}

function openTutor() {
    document.body.classList.remove("home-active");
    window.location.hash = "tutor";
    requestAnimationFrame(() => userInput?.focus());
}

startTutorButtons.forEach(button => {
    button.addEventListener("click", openTutor);
});

startScienceButtons.forEach(button => {
    button.addEventListener("click", () => {
        window.location.href = "/science";
    });
});

if (window.location.hash === "#tutor") {
    document.body.classList.remove("home-active");
}

function updateTokenCount(n) {
    if (tokenCount) tokenCount.textContent = n.toLocaleString();
}

function createAiSettingsDialog() {
    const dialog = document.createElement("div");
    dialog.className = "ai-settings-modal";
    dialog.id = "aiSettingsModal";
    dialog.hidden = true;
    dialog.innerHTML = `
        <div class="ai-settings-backdrop" data-ai-settings-close></div>
        <section class="ai-settings-panel" role="dialog" aria-modal="true" aria-labelledby="aiSettingsTitle">
            <div class="ai-settings-header">
                <div>
                    <p class="ai-settings-kicker">AI setup</p>
                    <h2 id="aiSettingsTitle">Choose your AI</h2>
                </div>
                <button class="ai-settings-close" type="button" data-ai-settings-close aria-label="Close AI settings">x</button>
            </div>
            <form id="aiSettingsForm" class="ai-settings-form">
                <label for="aiProviderSelect">AI provider</label>
                <select id="aiProviderSelect" name="provider">
                    <option value="groq">Groq</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="google">Google Gemini</option>
                    <option value="mistral">Mistral</option>
                    <option value="together">Together AI</option>
                    <option value="xai">xAI</option>
                    <option value="deepseek">DeepSeek</option>
                </select>

                <label for="aiApiKeyInput">API key</label>
                <input id="aiApiKeyInput" name="api_key" type="password" autocomplete="off" placeholder="Paste your API key" />

                <p class="ai-settings-help">
                    The key stays on this computer while the app is running. It is not saved in git.
                </p>

                <p class="ai-settings-message" id="aiSettingsMessage" hidden></p>

                <div class="ai-settings-actions">
                    <button class="secondary-settings-btn" type="button" data-ai-settings-close>Cancel</button>
                    <button class="primary-settings-btn" type="submit">Save</button>
                </div>
            </form>
        </section>
    `;
    document.body.appendChild(dialog);
    return dialog;
}

const aiSettingsModal = createAiSettingsDialog();
const aiSettingsForm = document.getElementById("aiSettingsForm");
const aiProviderSelect = document.getElementById("aiProviderSelect");
const aiApiKeyInput = document.getElementById("aiApiKeyInput");
const aiSettingsMessage = document.getElementById("aiSettingsMessage");

function getAiProviderLabel(providerId) {
    const provider = (aiSettingsStatus.providers || []).find(item => item.id === providerId);
    return provider ? provider.label : "AI";
}

function updateAiSettingsButton() {
    if (!aiSettingsBtn) return;
    const provider = getAiProviderLabel(aiSettingsStatus.provider);
    aiSettingsBtn.textContent = aiSettingsStatus.configured ? `AI: ${provider}` : "Set AI Key";
    aiSettingsBtn.classList.toggle("needs-key", !aiSettingsStatus.configured);
}

function showAiSettingsMessage(message, isError = false) {
    if (!aiSettingsMessage) return;
    aiSettingsMessage.textContent = message;
    aiSettingsMessage.hidden = false;
    aiSettingsMessage.classList.toggle("is-error", isError);
}

function openAiSettings(message = "") {
    aiProviderSelect.value = aiSettingsStatus.provider || "groq";
    aiApiKeyInput.value = "";
    if (message) showAiSettingsMessage(message, true);
    else aiSettingsMessage.hidden = true;
    aiSettingsModal.hidden = false;
    requestAnimationFrame(() => aiApiKeyInput.focus());
}

function closeAiSettings() {
    aiSettingsModal.hidden = true;
}

async function loadAiSettingsStatus() {
    try {
        const res = await fetch("/ai-settings");
        if (!res.ok) return;
        aiSettingsStatus = await res.json();
        if (Array.isArray(aiSettingsStatus.providers) && aiSettingsStatus.providers.length > 0) {
            aiProviderSelect.innerHTML = aiSettingsStatus.providers
                .map(provider => `<option value="${provider.id}">${provider.label}</option>`)
                .join("");
        }
        updateAiSettingsButton();
        openAiSettings("Choose the AI provider and paste the API key you want to use.");
    } catch (err) {
        console.error("[AI SETTINGS] status error:", err);
    }
}

if (aiSettingsBtn) {
    aiSettingsBtn.addEventListener("click", () => openAiSettings());
}

aiSettingsModal.addEventListener("click", event => {
    if (event.target.closest("[data-ai-settings-close]")) {
        closeAiSettings();
    }
});

aiSettingsForm.addEventListener("submit", async event => {
    event.preventDefault();
    const provider = aiProviderSelect.value;
    const apiKey = aiApiKeyInput.value.trim();
    if (!apiKey) {
        showAiSettingsMessage("Paste your API key first.", true);
        return;
    }

    try {
        const res = await fetch("/ai-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider, api_key: apiKey }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
            showAiSettingsMessage(data?.error || "Could not save AI settings.", true);
            return;
        }
        aiSettingsStatus = data;
        updateAiSettingsButton();
        showAiSettingsMessage("Saved. You can ask the tutor now.");
        setTimeout(closeAiSettings, 700);
    } catch (err) {
        showAiSettingsMessage("Network error. Try again.", true);
    }
});

function getTutorWelcomeHtml() {
    if (isScienceMode) {
        return `
        <div class="message assistant">
            <div class="message-content tutor-welcome">
                <p class="welcome-kicker">Bring one science idea at a time.</p>
                <h2>Build the concept, then test the reasoning.</h2>
                <p>
                    Ask about a concept, a vocabulary word, a formula, a practice question, or your own explanation.
                    I will help you separate the main idea from the wording and check the evidence behind it.
                </p>
                <div class="starter-prompts" aria-label="Science starter prompts">
                    <button type="button" data-prompt="Explain photosynthesis in simple words">Explain a concept</button>
                    <button type="button" data-prompt="What does erosion mean in Earth science?">Define vocabulary</button>
                    <button type="button" data-prompt="What does F = ma mean in real life?">Connect a formula</button>
                    <button type="button" data-prompt="Check my reasoning: a chemical reaction creates new atoms">Check reasoning</button>
                    <button type="button" data-prompt="Give me a practice question about ecosystems">Practice a concept</button>
                </div>
            </div>
        </div>`;
    }

    return `
        <div class="message assistant">
            <div class="message-content tutor-welcome">
                <p class="welcome-kicker">Start with the problem in front of you.</p>
                <h2>Delphic AI helps you reason through the next step.</h2>
                <p>
                    Ask for a solution, a simpler explanation, a work check, practice, or a graph.
                    I will keep the focus on understanding the idea behind the answer.
                </p>
                <div class="starter-prompts" aria-label="Starter prompts">
                    <button type="button" data-prompt="Solve 2x + 3 = 11">Solve an equation</button>
                    <button type="button" data-prompt="Explain the chain rule in simple language">Explain a concept</button>
                    <button type="button" data-prompt="I got x = 5. Is that right for 2x + 3 = 11?">Check my work</button>
                    <button type="button" data-prompt="Give me a practice problem about solving linear equations">Give me practice</button>
                    <button type="button" data-prompt="Graph y = x^2 - 4">Graph a function</button>
                </div>
            </div>
        </div>`;
}

function loadStepByStepMode() {
    if (!stepByStepToggle) return;
    stepByStepToggle.checked = localStorage.getItem(`${tutorMode}-tutor-step-mode`) === "true";
    updateStepModeNote();
}

function isStepByStepModeOn() {
    return Boolean(stepByStepToggle?.checked);
}

function updateStepModeNote() {
    if (!stepModeNote || !stepByStepToggle) return;
    stepModeNote.hidden = !stepByStepToggle.checked;
}

if (stepByStepToggle) {
    loadStepByStepMode();
    stepByStepToggle.addEventListener("change", () => {
        localStorage.setItem(`${tutorMode}-tutor-step-mode`, String(stepByStepToggle.checked));
        updateStepModeNote();
    });
}

// ---- Theme ----
const themes = ["light", "dark", "neon"];
const themeLabels = {
    light: "🌙 Light",
    dark: "☀️ Dark",
    neon: "✨ Neon"
};

function getSavedTheme() {
    const saved = localStorage.getItem("math-tutor-theme") || "dark";
    return themes.includes(saved) ? saved : "dark";
}

function setThemeMenuOpen(isOpen) {
    themeMenu.hidden = !isOpen;
    themeToggle.setAttribute("aria-expanded", String(isOpen));
}

function getSelectedThemeOption() {
    return Array.from(themeOptions).find(option => option.classList.contains("is-selected")) || themeOptions[0];
}

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    themeToggle.textContent = themeLabels[theme];
    themeToggle.title = `Current theme: ${theme}.`;
    themeOptions.forEach(option => {
        const isSelected = option.dataset.themeChoice === theme;
        option.classList.toggle("is-selected", isSelected);
        option.setAttribute("aria-checked", String(isSelected));
    });
}

function loadTheme() {
    applyTheme(getSavedTheme());
    setThemeMenuOpen(false);
}

themeToggle.addEventListener("click", event => {
    event.stopPropagation();
    const isOpen = themeToggle.getAttribute("aria-expanded") === "true";
    setThemeMenuOpen(!isOpen);
});

themeOptions.forEach(option => {
    option.addEventListener("click", event => {
        event.stopPropagation();
        const next = themes.includes(option.dataset.themeChoice) ? option.dataset.themeChoice : "light";
        localStorage.setItem("math-tutor-theme", next);
        applyTheme(next);
        setThemeMenuOpen(false);
        themeToggle.focus();
    });
});

document.addEventListener("click", () => {
    setThemeMenuOpen(false);
});

document.addEventListener("keydown", event => {
    const isThemeMenuOpen = themeToggle.getAttribute("aria-expanded") === "true";
    if (event.key === "Escape" && isThemeMenuOpen) {
        setThemeMenuOpen(false);
        themeToggle.focus();
        return;
    }

    if (event.key === "Escape" && sidebar.classList.contains("open")) {
        sidebar.classList.remove("open");
        menuBtn.focus();
    }
});

themeToggle.addEventListener("keydown", event => {
    if (event.key === "ArrowDown") {
        event.preventDefault();
        setThemeMenuOpen(true);
        getSelectedThemeOption()?.focus();
    }
});

themeOptions.forEach((option, index) => {
    option.addEventListener("keydown", event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const nextIndex = (index + direction + themeOptions.length) % themeOptions.length;
            themeOptions[nextIndex].focus();
        }

        if (event.key === "Home") {
            event.preventDefault();
            themeOptions[0]?.focus();
        }

        if (event.key === "End") {
            event.preventDefault();
            themeOptions[themeOptions.length - 1]?.focus();
        }

        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            option.click();
        }
    });
});

themePicker.addEventListener("focusout", () => {
    requestAnimationFrame(() => {
        if (!themePicker.contains(document.activeElement)) {
            setThemeMenuOpen(false);
        }
    });
});

loadTheme();

// ---- Load conversation history on page start ----
async function loadHistory() {
    try {
        const res = await fetch(apiUrl("/history"));
        const data = await res.json();
        if (data.messages && data.messages.length > 0) {
            chatMessages.innerHTML = "";
            data.messages.forEach(msg => addMessage(msg.role, msg.content));
        }
        if (data.tokens_used !== undefined) updateTokenCount(data.tokens_used);
    } catch (e) {
        console.warn("[HISTORY] Could not load history:", e);
    }
}

loadHistory();

// ---- Session management ----
const newChatBtn = document.getElementById("newChatBtn");
const currentSessionPreview = document.getElementById("currentSessionPreview");
const pastSessionsList = document.getElementById("pastSessionsList");

async function loadSessions() {
    try {
        const res = await fetch(apiUrl("/sessions"));
        const data = await res.json();
        renderSessions(data.current_session_id, data.sessions);
    } catch (e) {
        console.warn("[SESSIONS] Could not load sessions:", e);
    }
}

function renderSessions(currentId, sessions) {
    const past = sessions.filter(s => s.session_id !== currentId);
    const current = sessions.find(s => s.session_id === currentId);

    // Update current session preview
    if (currentSessionPreview) {
        currentSessionPreview.textContent = current ? current.preview : "New conversation";
    }

    // Render past sessions
    if (!pastSessionsList) return;
    if (past.length === 0) {
        pastSessionsList.innerHTML = `<li class="no-sessions-placeholder">No past sessions yet</li>`;
        return;
    }
    pastSessionsList.innerHTML = "";
    past.forEach(s => {
        const li = document.createElement("li");
        const date = s.last_active ? new Date(s.last_active).toLocaleDateString() : "";
        const preview = document.createElement("div");
        preview.classList.add("session-preview");
        preview.textContent = s.preview;

        const meta = document.createElement("div");
        meta.classList.add("session-meta");
        meta.textContent = `${date} · ${Math.floor(s.message_count / 2)} questions`;

        li.title = s.preview;
        li.addEventListener("click", () => switchToSession(s.session_id));
        li.append(preview, meta);
        pastSessionsList.appendChild(li);
    });
}

async function switchToSession(sessionId) {
    try {
        const res = await fetch(apiUrl("/sessions/switch"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        // Reload chat with that session's messages
        chatMessages.innerHTML = "";
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => addMessage(msg.role, msg.content));
        } else {
            chatMessages.innerHTML = getTutorWelcomeHtml();
        }
        if (data.tokens_used !== undefined) updateTokenCount(data.tokens_used);
        await loadSessions();
        sidebar.classList.remove("open");
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (e) {
        console.warn("[SESSIONS] Switch failed:", e);
    }
}

if (newChatBtn) {
    newChatBtn.addEventListener("click", async () => {
        try {
            await fetch(apiUrl("/sessions/new"), { method: "POST" });
            chatMessages.innerHTML = getTutorWelcomeHtml();
            updateTokenCount(0);
            await loadSessions();
            sidebar.classList.remove("open");
        } catch (e) {
            console.warn("[SESSIONS] New session failed:", e);
        }
    });
}

loadSessions();


menuBtn.addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("click", (e) => {
    if (
        sidebar.classList.contains("open") &&
        !sidebar.contains(e.target) &&
        e.target !== menuBtn
    ) {
        sidebar.classList.remove("open");
    }
});

window.addEventListener("resize", () => {
    if (window.innerWidth > 768) {
        sidebar.classList.remove("open");
        setThemeMenuOpen(false);
    }
});

// ---- Auto-resize textarea + character counter ----
const charCounter = document.getElementById("charCounter");
userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = userInput.scrollHeight + "px";
    const len = userInput.value.length;
    if (charCounter) {
        charCounter.textContent = len > 1800 ? `${len}/2000` : "";
        charCounter.style.color = len > 1950 ? "#ef4444" : "#f59e0b";
    }
});

// ---- Render math (KaTeX) in a container ----
function renderMath(container) {
    if (typeof renderMathInElement === "function") {
        renderMathInElement(container, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "\\[", right: "\\]", display: true },
                { left: "\\(", right: "\\)", display: false },
                { left: "$", right: "$", display: false },
            ],
            ignoredTags: ["script", "noscript", "style", "textarea", "pre"],
            throwOnError: false,
            trust: true,
        });
    }
}

// ---- Normalize LaTeX delimiters + protect from Markdown ----
function protectLatex(text) {
    const blocks = [];

    const store = (content, display) => {
        const wrapped = display ? `$$${content}$$` : `\\(${content}\\)`;
        blocks.push(wrapped);
        return `%%MATH_BLOCK_${blocks.length - 1}%%`;
    };

    // ── Display math — all known variants → $$ ... $$ ──

    // \begin{equation[*]} ... \end{equation[*]}
    text = text.replace(/\\begin\{equation\*?\}([\s\S]*?)\\end\{equation\*?\}/g,
        (_, inner) => store(inner.trim(), true));

    // \begin{align[*]} ... \end{align[*]}
    text = text.replace(/\\begin\{align\*?\}([\s\S]*?)\\end\{align\*?\}/g,
        (_, inner) => store(inner.trim(), true));

    // \begin{aligned} ... \end{aligned}
    text = text.replace(/\\begin\{aligned\}([\s\S]*?)\\end\{aligned\}/g,
        (_, inner) => store(inner.trim(), true));

    // \[ ... \]
    text = text.replace(/\\\[([\s\S]*?)\\\]/g,
        (_, inner) => store(inner.trim(), true));

    // $$ ... $$ (already correct format)
    text = text.replace(/\$\$([\s\S]*?)\$\$/g,
        (_, inner) => store(inner.trim(), true));

    // Bare [ ... ] on its own line (the AI's most common mistake)
    // Guard: must not look like a markdown link [text](url) or checkbox [x]
    text = text.replace(/(?:^|\n)[ \t]*\[([^\[\]\n]{2,})\][ \t]*(?=\n|$)/g,
        (match, inner) => {
            // Skip if it looks like a markdown link target or short label
            if (/^\s*(x| )\s*$/.test(inner)) return match; // checkbox
            return `\n${store(inner.trim(), true)}\n`;
        });

    // ── Inline math — all known variants → \( ... \) ──

    // \( ... \) (already correct format)
    text = text.replace(/\\\(([\s\S]*?)\\\)/g,
        (_, inner) => store(inner, false));

    // Single $ ... $ (but not $$)
    text = text.replace(/(?<!\$)\$(?!\$)((?:[^$\n\\]|\\.)+?)\$(?!\$)/g,
        (_, inner) => store(inner, false));

    return { text, blocks };
}

function restoreLatex(html, blocks) {
    return html.replace(/%%MATH_BLOCK_(\d+)%%/g, (_, i) => blocks[parseInt(i)]);
}

// ---- Render Markdown (with LaTeX protection) ----
function renderMarkdown(text) {
    if (typeof marked !== "undefined") {
        const { text: protectedText, blocks } = protectLatex(text);
        const html = marked.parse(protectedText);
        return restoreLatex(html, blocks);
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

function sanitizeRenderedHtml(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    const allowedTags = new Set([
        "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3",
        "h4", "h5", "h6", "hr", "li", "ol", "p", "pre", "strong",
        "table", "tbody", "td", "th", "thead", "tr", "ul",
    ]);

    template.content.querySelectorAll("*").forEach(node => {
        const tag = node.tagName.toLowerCase();
        if (!allowedTags.has(tag)) {
            node.remove();
            return;
        }

        Array.from(node.attributes).forEach(attr => {
            const name = attr.name.toLowerCase();
            const allowed = (tag === "a" && ["href", "title"].includes(name))
                || (tag === "code" && name === "class");
            if (!allowed) {
                node.removeAttribute(attr.name);
            }
        });

        if (tag === "a" && node.hasAttribute("href")) {
            try {
                const url = new URL(node.getAttribute("href"), window.location.origin);
                if (!["http:", "https:", "mailto:"].includes(url.protocol)) {
                    node.removeAttribute("href");
                }
            } catch {
                node.removeAttribute("href");
            }
            node.setAttribute("rel", "noopener noreferrer");
        }
    });

    return template.innerHTML;
}

function renderSafeMarkdown(text) {
    return sanitizeRenderedHtml(renderMarkdown(text));
}

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

// ---- Format timestamp ----
function getTimestamp() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ---- Add a message to the chat ----
// ---- Confidence badge ----
// Strips "CONFIDENCE: High/Medium/Low" from the text and returns { cleanText, level }
function extractConfidence(text) {
    const match = text.match(/\nCONFIDENCE:\s*(High|Medium|Low)\s*$/i);
    if (!match) return { cleanText: text, level: null };
    return {
        cleanText: text.slice(0, match.index).trimEnd(),
        level: match[1].charAt(0).toUpperCase() + match[1].slice(1).toLowerCase(),
    };
}

function createConfidenceBadge(level) {
    if (!level) return null;
    const badge = document.createElement("span");
    badge.classList.add("confidence-badge", `confidence-${level.toLowerCase()}`);
    badge.textContent = `${level} confidence`;
    return badge;
}

function createPracticeButton() {
    const practiceBtn = document.createElement("button");
    practiceBtn.classList.add("practice-btn");
    practiceBtn.type = "button";
    practiceBtn.textContent = practiceButtonLabel;
    practiceBtn.addEventListener("click", () => requestPracticeProblem(practiceBtn));
    return practiceBtn;
}

function addMessage(role, content) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", role);

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");

    if (role === "assistant") {
        const { cleanText, level } = extractConfidence(content);
        contentDiv.innerHTML = renderSafeMarkdown(cleanText);
        const badge = createConfidenceBadge(level);
        if (badge) contentDiv.appendChild(badge);
    } else {
        contentDiv.textContent = content;
    }

    // Timestamp
    const timeEl = document.createElement("span");
    timeEl.classList.add("message-time");
    timeEl.textContent = getTimestamp();
    contentDiv.appendChild(timeEl);

    msgDiv.appendChild(contentDiv);

    // Add copy button for assistant messages
    if (role === "assistant") {
        const copyBtn = document.createElement("button");
        copyBtn.classList.add("copy-btn");
        copyBtn.innerHTML = "Copy";
        copyBtn.addEventListener("click", () => {
            navigator.clipboard.writeText(content).then(() => {
                copyBtn.innerHTML = "Copied";
                copyBtn.classList.add("copied");
                setTimeout(() => {
                    copyBtn.innerHTML = "Copy";
                    copyBtn.classList.remove("copied");
                }, 2000);
            });
        });
        msgDiv.appendChild(copyBtn);
        msgDiv.appendChild(createPracticeButton());
    }

    chatMessages.appendChild(msgDiv);

    // Render LaTeX after DOM insertion
    if (role === "assistant") {
        renderMath(contentDiv);
    }

    scrollToBottom();
}

// ---- Streaming bubble ----
// Creates an empty assistant bubble and returns references to update it live.
function createStreamingBubble() {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");

    const textEl = document.createElement("div");
    textEl.classList.add("message-text");
    contentDiv.appendChild(textEl);

    // Timestamp
    const timeEl = document.createElement("span");
    timeEl.classList.add("message-time");
    timeEl.textContent = getTimestamp();
    contentDiv.appendChild(timeEl);

    msgDiv.appendChild(contentDiv);

    // Copy button — added now so it's always present; text is set on [DONE]
    const copyBtn = document.createElement("button");
    copyBtn.classList.add("copy-btn");
    copyBtn.innerHTML = "Copy";
    copyBtn.style.display = "none"; // hidden until streaming is complete
    msgDiv.appendChild(copyBtn);

    chatMessages.appendChild(msgDiv);
    scrollToBottom();

    const practiceBtn = createPracticeButton();
    practiceBtn.style.display = "none";
    msgDiv.appendChild(practiceBtn);

    return { bubble: msgDiv, contentDiv, textEl, copyBtn, practiceBtn };
}

// ---- Typing indicator ----
function showTyping() {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");
    msgDiv.id = "typingIndicator";

    msgDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span><span></span><span></span>
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

function hideTyping() {
    const el = document.getElementById("typingIndicator");
    if (el) el.remove();
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// ---- Show / hide loading spinner on send button ----
const sendBtnDefaultHTML = sendBtn.innerHTML;

function showSpinner() {
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="send-spinner"></div>';
}

function hideSpinner() {
    sendBtn.disabled = false;
    sendBtn.innerHTML = sendBtnDefaultHTML;
}

// ---- Input validation warning ----
function showWarning(msg) {
    let warning = document.querySelector(".input-warning");
    if (!warning) {
        warning = document.createElement("p");
        warning.classList.add("input-warning");
        document.querySelector(".chat-input-area").appendChild(warning);
    }
    warning.textContent = msg;
    setTimeout(() => { warning.textContent = ""; }, 3000);
}

function formatExportDate(date = new Date()) {
    return date.toISOString().slice(0, 19).replace("T", "_").replace(/:/g, "-");
}

function buildTranscriptHtml(messages) {
    const exportedAt = new Date().toLocaleString();
    const messageHtml = messages.map((msg) => {
        const role = msg.role === "assistant" ? "Tutor" : "Student";
        const rawContent = String(msg.content || "");
        const content = msg.role === "assistant"
            ? extractConfidence(rawContent).cleanText
            : rawContent;
        const body = msg.role === "assistant"
            ? renderSafeMarkdown(content.trim())
            : `<p>${escapeHtml(content.trim()).replace(/\n/g, "<br>")}</p>`;

        return `
            <article class="message ${msg.role}">
                <div class="role">${role}</div>
                <div class="bubble">${body}</div>
            </article>
        `;
    }).join("\n");

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Delphic AI Chat Export</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f8fafc;
            --paper: #ffffff;
            --ink: #111827;
            --muted: #64748b;
            --line: #e2e8f0;
            --student: #eef2ff;
            --tutor: #ffffff;
            --accent: #0f766e;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.65;
        }

        main {
            width: min(860px, calc(100% - 32px));
            margin: 0 auto;
            padding: 40px 0 56px;
        }

        header {
            margin-bottom: 28px;
            padding-bottom: 18px;
            border-bottom: 1px solid var(--line);
        }

        h1 {
            margin: 0;
            font-size: 32px;
            line-height: 1.15;
        }

        .meta {
            margin-top: 8px;
            color: var(--muted);
            font-size: 14px;
        }

        .message {
            margin: 18px 0;
        }

        .role {
            margin-bottom: 6px;
            color: var(--muted);
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .bubble {
            border: 1px solid var(--line);
            border-radius: 12px;
            background: var(--tutor);
            padding: 16px 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            overflow-wrap: anywhere;
        }

        .student .bubble {
            background: var(--student);
            border-color: #c7d2fe;
        }

        .tutor .role {
            color: var(--accent);
        }

        p { margin: 0 0 10px; }
        p:last-child { margin-bottom: 0; }
        pre {
            overflow-x: auto;
            padding: 12px;
            border-radius: 8px;
            background: #0f172a;
            color: #e2e8f0;
        }
        code {
            font-family: "SFMono-Regular", Consolas, monospace;
        }
        .katex-display {
            overflow-x: auto;
            overflow-y: hidden;
            padding: 4px 0;
        }
    </style>
</head>
<body>
    <main>
        <header>
            <h1>Delphic AI Chat Export</h1>
            <div class="meta">Exported ${escapeHtml(exportedAt)}</div>
        </header>
        ${messageHtml}
    </main>
</body>
</html>`;
}

// ---- Download current chat to this laptop ----
function downloadFile(filename, content, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function showDownloadHelp(filename) {
    document.querySelector(".download-help")?.remove();

    const notice = document.createElement("section");
    notice.className = "download-help";
    notice.setAttribute("role", "status");
    notice.setAttribute("aria-live", "polite");

    const title = document.createElement("strong");
    title.textContent = "Your chat download has started";

    const filenameText = document.createElement("p");
    filenameText.className = "download-help-filename";
    filenameText.textContent = filename;

    const instructions = document.createElement("p");
    instructions.textContent = "Find it in Downloads: open File Explorer on Windows or Finder on Mac, then choose Downloads. If your browser asked where to save it, look in the folder you selected.";

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.textContent = "Got it";
    closeButton.addEventListener("click", () => notice.remove());

    notice.append(title, filenameText, instructions, closeButton);
    document.body.appendChild(notice);
    closeButton.focus();
}

async function downloadCurrentChat() {
    if (!downloadChatBtn) return;

    try {
        downloadChatBtn.textContent = "Preparing...";
        downloadChatBtn.disabled = true;

        const historyRes = await fetch(apiUrl("/history"));
        const history = await historyRes.json();
        const messages = history.messages || [];

        if (messages.length === 0) {
            showWarning("There is no chat to download yet.");
            return;
        }

        const transcript = buildTranscriptHtml(messages);
        const filename = `delphic-${tutorMode}-chat-${formatExportDate()}.html`;
        downloadFile(filename, transcript, "text/html;charset=utf-8");
        showDownloadHelp(filename);
    } catch (err) {
        console.error("[CHAT DOWNLOAD]", err);
        showWarning(err.message || "Could not download chat.");
    } finally {
        downloadChatBtn.textContent = downloadButtonLabel;
        downloadChatBtn.disabled = false;
    }
}

if (downloadChatBtn) {
    downloadChatBtn.addEventListener("click", downloadCurrentChat);
}

async function requestPracticeProblem(button) {
    if (button) {
        button.disabled = true;
        button.textContent = "Making practice...";
    }

    try {
        await sendMessage(practicePrompt, { practiceMode: true });
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = practiceButtonLabel;
        }
    }
}

async function requestScienceQuiz(button) {
    if (!isScienceMode) return;

    if (button) {
        button.disabled = true;
        button.textContent = "Starting quiz...";
    }

    try {
        await sendMessage(quizPrompt, { quizMode: true });
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = quizButtonLabel;
        }
    }
}

if (quizModeBtn) {
    quizModeBtn.addEventListener("click", () => requestScienceQuiz(quizModeBtn));
}

// ---- Add graph to the chat ----
function addDesmosGraph(plotData) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");
    contentDiv.classList.add("graph-card");

    const graphId = `desmos-${Date.now()}`;
    const label = plotData.equation_latex || "";
    const title = plotData.type === "points" ? "Interactive point plot" : "Interactive graph";
    const header = document.createElement("div");
    header.classList.add("graph-card-header");

    const titleEl = document.createElement("span");
    titleEl.textContent = title;

    const labelEl = document.createElement("strong");
    labelEl.textContent = `\\(${label}\\)`;

    const graphEl = document.createElement("div");
    graphEl.classList.add("desmos-container");
    graphEl.id = graphId;

    header.append(titleEl, labelEl);
    contentDiv.append(header, graphEl);

    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);

    // Init Desmos after the element is in the DOM
    requestAnimationFrame(() => {
        const el = document.getElementById(graphId);
        if (!el) return;
        if (typeof Desmos === "undefined") {
            el.innerHTML = '<div class="graph-error">The graph tool did not load. Please refresh and try again.</div>';
            return;
        }

        const calc = Desmos.GraphingCalculator(el, {
            expressionsCollapsed: true,
            settingsMenu: false,
            zoomButtons: true,
            lockViewport: false,
        });

        if (plotData.type === "function") {
            calc.setExpression({ id: "g1", latex: plotData.desmos_latex });
        } else if (plotData.type === "points" && plotData.desmos_exprs) {
            plotData.desmos_exprs.forEach((expr, i) => {
                calc.setExpression({ id: `p${i}`, latex: expr, color: Desmos.Colors.BLUE });
            });
        }
    });

    renderMath(contentDiv);
    scrollToBottom();
}

// ---- Send message ----
async function sendMessage(messageOverride = null, options = {}) {
    const text = (messageOverride ?? userInput.value).trim();
    if (!text) return;
    if (isSending) {
        showWarning("Please wait for the current answer to finish.");
        return;
    }

    // Input validation
    if (text.length < 3) {
        showWarning(isScienceMode ? "Too short. Try typing a full science question." : "Too short. Try typing a full math question.");
        userInput.focus();
        return;
    }

    isSending = true;
    addMessage("user", text);
    if (messageOverride === null) {
        userInput.value = "";
        userInput.style.height = "auto";
    }
    showSpinner();
    showTyping();

    // Fire plot request in parallel if needed
    const isPlotRequest = /\b(plot|graph|draw|sketch|chart)\b/i.test(text)
                       || /^\s*y\s*=\s*.+/i.test(text)
                       || /^\s*f\s*\(\s*x\s*\)\s*=\s*.+/i.test(text);
    let plotPromise = null;
    if (graphingEnabled && isPlotRequest) {
        plotPromise = fetch("/plot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text }),
        }).catch(err => {
            console.error("[PLOT] fetch error:", err);
            return null;
        });
    }

    try {
        const res = await fetch(apiUrl("/stream"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: text,
                hint_mode: false,
                check_mode: false,
                step_by_step_mode: isStepByStepModeOn(),
                practice_mode: Boolean(options.practiceMode),
                quiz_mode: Boolean(options.quizMode),
            }),
        });

        if (!res.ok) {
            hideTyping();
            const errData = await res.json().catch(() => null);
            const errorMessage = errData?.error || "Something went wrong. Please try again.";
            showWarning(errorMessage);
            if (/provider|api key/i.test(errorMessage)) {
                openAiSettings(errorMessage);
            }
            hideSpinner();
            userInput.focus();
            return;
        }

        // Create an empty assistant bubble to stream into
        hideTyping();
        const { bubble, contentDiv, textEl, copyBtn, practiceBtn } = createStreamingBubble();
        let accumulated = "";

        // Word-by-word queue — chunks split into words, each word pops in with a short delay
        const wordQueue = [];
        let isPopping = false;
        const WORD_DELAY_MS = 18; // ms between each word — tweak to taste

        function popWord() {
            if (wordQueue.length === 0) {
                isPopping = false;
                return;
            }
            isPopping = true;
            accumulated += wordQueue.shift();
            textEl.innerHTML = sanitizeRenderedHtml(marked.parse(accumulated));
            scrollToBottom();
            setTimeout(popWord, WORD_DELAY_MS);
        }

        function enqueueWords(text) {
            // Split on spaces but keep the space attached to each word
            const words = text.split(/(?<= )/);
            for (const word of words) wordQueue.push(word);
            if (!isPopping) popWord();
        }

        function waitForQueue() {
            return new Promise(resolve => {
                function check() {
                    if (wordQueue.length === 0 && !isPopping) resolve();
                    else setTimeout(check, 50);
                }
                check();
            });
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const payload = line.slice(6);

                if (payload.startsWith("[DONE:")) {
                    await waitForQueue();
                    const tokens = parseInt(payload.slice(6, -1), 10);
                    if (!isNaN(tokens)) updateTokenCount(tokens);
                    loadSessions(); // refresh sidebar session preview
                    // Strip confidence line, then run renderMarkdown (which calls
                    // protectLatex) so ALL bracket variants are normalised before KaTeX
                    const { cleanText, level } = extractConfidence(accumulated.replace(/\\n/g, "\n"));
                    textEl.innerHTML = renderSafeMarkdown(cleanText);
                    // Append confidence badge if present
                    const badge = createConfidenceBadge(level);
                    if (badge) contentDiv.appendChild(badge);
                    renderMathInElement(bubble, {
                        delimiters: [
                            { left: "$$", right: "$$", display: true },
                            { left: "\\(", right: "\\)", display: false },
                            { left: "\\[", right: "\\]", display: true },
                        ],
                        throwOnError: false,
                    });
                    // Show copy button now that we have the final text
                    copyBtn.style.display = "";
                    practiceBtn.style.display = "";
                    copyBtn.addEventListener("click", () => {
                        navigator.clipboard.writeText(cleanText).then(() => {
                            copyBtn.innerHTML = "Copied";
                            copyBtn.classList.add("copied");
                            setTimeout(() => {
                                copyBtn.innerHTML = "Copy";
                                copyBtn.classList.remove("copied");
                            }, 2000);
                        });
                    });
                    scrollToBottom();
                } else {
                    enqueueWords(payload.replace(/\\n/g, "\n"));
                }
            }
        }
    } catch (err) {
        hideTyping();
        addMessage("assistant", "Network error. Please check your connection.");
    } finally {
        hideSpinner();
        userInput.focus();

        // Show graph if we got one
        if (plotPromise) {
            try {
                const plotRes = await plotPromise;
                if (plotRes) {
                    const plotData = await plotRes.json();
                    if (plotRes.ok && plotData.type) {
                        addDesmosGraph(plotData);
                    } else if (!plotRes.ok) {
                        showWarning(plotData.error || "I could not graph that. Try: plot y = x^2.");
                    }
                }
            } catch (plotErr) {
                console.error("[PLOT] parse error:", plotErr);
                showWarning("I could not load the graph. Please try a simpler equation.");
            }
        }
        isSending = false;
    }
}

sendBtn.addEventListener("click", sendMessage);
userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

homePromptButtons.forEach(button => {
    button.addEventListener("click", () => {
        openTutor();
        userInput.value = button.getAttribute("data-home-prompt") || "";
        userInput.dispatchEvent(new Event("input"));
        userInput.focus();
    });
});

// ---- Clear chat ----
clearBtn.addEventListener("click", async () => {
    await fetch(apiUrl("/clear"), { method: "POST" });
    chatMessages.innerHTML = getTutorWelcomeHtml();
    updateTokenCount(0);
    await loadSessions();
});

// ---- Sidebar topic / quick-action clicks ----
document.querySelectorAll("[data-topic]").forEach((el) => {
    el.addEventListener("click", () => {
        userInput.value = el.getAttribute("data-topic");
        userInput.focus();
        sidebar.classList.remove("open");
    });
});

document.addEventListener("click", event => {
    const promptButton = event.target.closest("[data-prompt]");
    if (promptButton) {
        userInput.value = promptButton.getAttribute("data-prompt");
        sendMessage();
        sidebar.classList.remove("open");
    }
});

loadAiSettingsStatus();
