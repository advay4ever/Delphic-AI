/**
 * Delphic AI - Client-side JavaScript
 */

const chatMessages = document.getElementById("chatMessages");
const chatInputArea = document.querySelector(".chat-input-area");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
window.addEventListener("attachment-warning", event => showWarning(event.detail));
window.addEventListener("attachment-selected", () => setImageModeActive(false));
const themeToggle = document.getElementById("themeToggle");
const themeMenu = document.getElementById("themeMenu");
const themeOptions = document.querySelectorAll("[data-theme-choice]");
const themePicker = themeToggle.closest(".theme-picker");
const menuBtn = document.getElementById("menuBtn");
const sidebar = document.getElementById("sidebar");
const sidebarResizeHandle = document.getElementById("sidebarResizeHandle");
const tokenCount = document.getElementById("tokenCount");
const sidebarChats = document.getElementById("sidebarChats");
const manageChatsBtn = document.getElementById("manageChatsBtn");
const chatManageActions = document.getElementById("chatManageActions");
const selectAllChatsBtn = document.getElementById("selectAllChatsBtn");
const deleteSelectedChatsBtn = document.getElementById("deleteSelectedChatsBtn");
const currentSessionItem = document.getElementById("currentSessionItem");
const currentSessionSelect = document.getElementById("currentSessionSelect");
const currentSessionActionsBtn = document.getElementById("currentSessionActionsBtn");
const stepByStepToggle = document.getElementById("stepByStepToggle");
const stepModeNote = document.getElementById("stepModeNote");
const quizModeBtn = document.getElementById("quizModeBtn");
const imageModeBtn = document.getElementById("imageModeBtn");
const imageModePicker = document.getElementById("imageModePicker");
const imageModeSelect = document.getElementById("imageModeSelect");
const aiSettingsBtn = document.getElementById("aiSettingsBtn");
const competitionPracticeBtn = document.getElementById("competitionPracticeBtn");
const competitionPicker = document.getElementById("competitionPicker");
const competitionMenu = document.getElementById("competitionMenu");
const competitionOptions = competitionMenu
    ? Array.from(competitionMenu.querySelectorAll(".competition-option"))
    : [];
const startTutorButtons = document.querySelectorAll("[data-start-tutor]");
const startScienceButtons = document.querySelectorAll("[data-start-science]");
const homePromptButtons = document.querySelectorAll("[data-home-prompt]");
const tutorMode = document.body.dataset.tutorMode || "math";
const apiBase = document.body.dataset.apiBase || "";
const graphingEnabled = document.body.dataset.graphingEnabled !== "false";
const imageGenerationEnabled = document.body.dataset.imageGenerationEnabled === "true";
const practicePrompt = document.body.dataset.practicePrompt || "Give me a similar practice problem.";
const practiceButtonLabel = document.body.dataset.practiceButtonLabel || "Practice Similar Problem";
const quizPrompt = document.body.dataset.quizPrompt || "Start a 5-question science quiz.";
const quizButtonLabel = document.body.dataset.quizButtonLabel || "Quiz Mode";
const isScienceMode = tutorMode === "science";
const sidebarWidthStorageKey = "delphic-sidebar-width";
const sidebarMinimumWidth = 220;
const sidebarDefaultWidth = 248;
const sidebarMaximumWidth = 420;
const maxContinuationsPerAnswer = 1;
const aiSettingsEventKey = "delphic-ai-settings-event";
const aiSettingsTabId = globalThis.crypto?.randomUUID?.()
    || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
const aiSettingsChannel = "BroadcastChannel" in globalThis
    ? new BroadcastChannel("delphic-ai-settings")
    : null;
let isSending = false;
let warningTimeout = null;
let aiSettingsStatus = {
    configured: false,
    provider: "groq",
    model: "",
    image_model: "openai/gpt-image-2.5-sunburst",
    image_models: [],
    providers: [],
    loaded: false,
};
let aiSettingsCloseTimeout = null;
let aiSettingsMutationVersion = 0;
let latestAiSettingsLoad = 0;
let aiSettingsDraftDirty = false;
let aiSettingsDraftVersion = 0;
let aiSettingsMutationPending = false;
let aiSettingsRefreshPending = false;
let lastAiSettingsFocus = null;
let deferredAiSettingsRequest = null;
let workspaceInertState = null;

function setWorkspaceModalActive(active) {
    if (active && !workspaceInertState) {
        workspaceInertState = new Map();
        document.querySelectorAll("#sidebar, .chat-main, #homePage").forEach(element => {
            workspaceInertState.set(element, element.inert);
            element.inert = true;
        });
        window.dispatchEvent(new Event("workspace-modal-opening"));
    } else if (!active && workspaceInertState) {
        workspaceInertState.forEach((inert, element) => { element.inert = inert; });
        workspaceInertState = null;
    }
    document.body.classList.toggle("workspace-modal-open", active);
}
let isReplacingAiKey = false;
let currentSessionDetails = null;
let availableSessions = [];
let isManagingChats = false;
const selectedSessionIds = new Set();
const requestedSessionTitles = new Set();

function updateComposerClearance() {
    if (!chatInputArea || !chatMessages) return;
    const composerHeight = Math.ceil(chatInputArea.getBoundingClientRect().height);
    if (composerHeight <= 0) return;
    const atBottom = chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight <= 2;
    chatMessages.style.setProperty("--composer-clearance", `${composerHeight}px`);
    if (atBottom && !chatMessages.querySelector(".welcome-message")) {
        chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: "instant" });
    }
}

if (chatInputArea) {
    updateComposerClearance();
    if ("ResizeObserver" in window) {
        const composerResizeObserver = new ResizeObserver(updateComposerClearance);
        composerResizeObserver.observe(chatInputArea);
    }
    window.addEventListener("resize", updateComposerClearance);
}
let activeSessionId = null;
const tabChatStorageKey = `delphic-active-chat-${tutorMode}`;
try { activeSessionId = sessionStorage.getItem(tabChatStorageKey) || null; } catch {}
let chatViewVersion = 0;
let chatViewAbort = new AbortController();
let chatNavigationTail = Promise.resolve();
let chatHistoryReady = false;
let historyPage = null;
let loadingEarlierMessages = false;
const MAX_TRANSCRIPT_MESSAGES = 10000;
const MAX_TRANSCRIPT_TEXT_BYTES = 32 * 1024 * 1024;
const MAX_TRANSCRIPT_IMAGE_BYTES = 64 * 1024 * 1024;
let sessionActionMenu = null;
let sessionActionTrigger = null;
// Preserve the saved-image identity used before corpus removal.
const imageOwnerStorageKey = "delphic-corpus-owner-id";
let temporaryImageOwnerId = "";
const fallbackModelsByProvider = {
    groq: [
        { id: "openai/gpt-oss-120b", label: "GPT-OSS 120B (recommended)" },
        { id: "openai/gpt-oss-20b", label: "GPT-OSS 20B" },
        { id: "llama-3.3-70b-versatile", label: "Llama 3.3 70B" },
        { id: "llama-3.1-8b-instant", label: "Llama 3.1 8B (fast)" },
    ],
    openai: [
        { id: "gpt-5.6-luna", label: "GPT-5.6 Luna (recommended)" },
        { id: "gpt-5.6-terra", label: "GPT-5.6 Terra (balanced)" },
        { id: "gpt-5.6-sol", label: "GPT-5.6 Sol (most capable)" },
        { id: "gpt-5.5", label: "GPT-5.5 (strong all-purpose)" },
        { id: "gpt-5.2", label: "GPT-5.2 (strong reasoning)" },
        { id: "gpt-5", label: "GPT-5 (strong reasoning)" },
        { id: "gpt-5-mini", label: "GPT-5 mini (fast and affordable)" },
        { id: "gpt-5-nano", label: "GPT-5 nano (fastest)" },
        { id: "gpt-4.1", label: "GPT-4.1 (strong all-purpose)" },
    ],
    anthropic: [
        { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5 (recommended: fast)" },
        { id: "claude-sonnet-5", label: "Claude Sonnet 5 (balanced)" },
        { id: "claude-opus-5", label: "Claude Opus 5 (advanced reasoning)" },
        { id: "claude-fable-5", label: "Claude Fable 5 (long-running work)" },
    ],
    google: [
        { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash (recommended)" },
        { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash" },
    ],
    mistral: [
        { id: "magistral-small-latest", label: "Magistral Small (recommended)" },
    ],
    together: [
        { id: "openai/gpt-oss-120b", label: "GPT-OSS 120B (recommended)" },
    ],
    xai: [
        { id: "grok-4.20-0309-reasoning", label: "Grok 4.20 Reasoning (recommended)" },
    ],
    deepseek: [
        { id: "deepseek-v4-pro", label: "DeepSeek V4 Pro (recommended)" },
    ],
    openrouter: [
        { id: "openai/gpt-5.6-terra", label: "GPT-5.6 Terra (recommended)" },
    ],
};

function apiUrl(path) {
    return `${apiBase}${path}`;
}

function canResizeSidebar() {
    return window.innerWidth > 768;
}

function getSidebarMaximumWidth() {
    return Math.max(
        sidebarMinimumWidth,
        Math.min(sidebarMaximumWidth, window.innerWidth - 440)
    );
}

function clampSidebarWidth(width) {
    return Math.round(Math.min(getSidebarMaximumWidth(), Math.max(sidebarMinimumWidth, width)));
}

function setSidebarWidth(width, persist = false) {
    if (!sidebar || !sidebarResizeHandle || !canResizeSidebar()) return;

    const nextWidth = clampSidebarWidth(width);
    document.documentElement.style.setProperty("--sidebar-width", `${nextWidth}px`);
    sidebarResizeHandle.setAttribute("aria-valuenow", String(nextWidth));
    sidebarResizeHandle.setAttribute("aria-valuemax", String(getSidebarMaximumWidth()));
    sidebarResizeHandle.setAttribute("aria-valuetext", `${nextWidth} pixels wide`);

    if (persist) {
        try {
            window.localStorage.setItem(sidebarWidthStorageKey, String(nextWidth));
        } catch (_error) {
            // A temporary width is still useful when browser storage is unavailable.
        }
    }
}

function loadSidebarWidth() {
    if (!sidebarResizeHandle || !canResizeSidebar()) return;

    let savedWidth = sidebarDefaultWidth;
    try {
        const storedWidth = Number.parseInt(window.localStorage.getItem(sidebarWidthStorageKey), 10);
        if (Number.isFinite(storedWidth)) savedWidth = storedWidth;
    } catch (_error) {
        // Use the standard width when browser storage is unavailable.
    }
    setSidebarWidth(savedWidth);
}

if (sidebarResizeHandle) {
    let activeResizePointerId = null;

    loadSidebarWidth();

    const finishSidebarResize = event => {
        if (activeResizePointerId === null || event.pointerId !== activeResizePointerId) return;
        const finalWidth = Number.parseInt(
            document.documentElement.style.getPropertyValue("--sidebar-width"),
            10
        );
        if (Number.isFinite(finalWidth)) setSidebarWidth(finalWidth, true);
        document.body.classList.remove("is-resizing-sidebar");
        if (sidebarResizeHandle.hasPointerCapture(event.pointerId)) {
            sidebarResizeHandle.releasePointerCapture(event.pointerId);
        }
        activeResizePointerId = null;
    };

    sidebarResizeHandle.addEventListener("pointerdown", event => {
        if (!canResizeSidebar() || event.button !== 0) return;
        event.preventDefault();
        activeResizePointerId = event.pointerId;
        sidebarResizeHandle.setPointerCapture(event.pointerId);
        document.body.classList.add("is-resizing-sidebar");
        setSidebarWidth(event.clientX);
    });

    sidebarResizeHandle.addEventListener("pointermove", event => {
        if (event.pointerId !== activeResizePointerId) return;
        setSidebarWidth(event.clientX);
    });

    sidebarResizeHandle.addEventListener("pointerup", finishSidebarResize);
    sidebarResizeHandle.addEventListener("pointercancel", finishSidebarResize);

    sidebarResizeHandle.addEventListener("keydown", event => {
        if (!canResizeSidebar()) return;

        const currentWidth = Number.parseInt(
            document.documentElement.style.getPropertyValue("--sidebar-width"),
            10
        ) || sidebarDefaultWidth;
        let nextWidth = currentWidth;

        if (event.key === "ArrowLeft") nextWidth -= 12;
        if (event.key === "ArrowRight") nextWidth += 12;
        if (event.key === "Home") nextWidth = sidebarMinimumWidth;
        if (event.key === "End") nextWidth = getSidebarMaximumWidth();
        if (nextWidth === currentWidth) return;

        event.preventDefault();
        setSidebarWidth(nextWidth, true);
    });
}

function createImageOwnerId() {
    const values = new Uint8Array(16);
    if (window.crypto?.getRandomValues) {
        window.crypto.getRandomValues(values);
    } else {
        for (let index = 0; index < values.length; index += 1) {
            values[index] = Math.floor(Math.random() * 256);
        }
    }
    values[6] = (values[6] & 0x0f) | 0x40;
    values[8] = (values[8] & 0x3f) | 0x80;
    const hex = Array.from(values, value => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function getImageOwnerId() {
    try {
        const savedId = window.localStorage.getItem(imageOwnerStorageKey);
        if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(savedId || "")) {
            return savedId;
        }
    } catch (_error) {
        // Some privacy settings block local storage; use this page's temporary ID instead.
    }

    if (!temporaryImageOwnerId) temporaryImageOwnerId = createImageOwnerId();
    try {
        window.localStorage.setItem(imageOwnerStorageKey, temporaryImageOwnerId);
    } catch (_error) {
        // The temporary ID still keeps requests together until the page is closed.
    }
    return temporaryImageOwnerId;
}

function getImageRequestHeaders(headers = {}) {
    return { ...headers, "X-Delphic-Corpus-Owner": getImageOwnerId(),
        ...(activeSessionId ? { "X-Delphic-Chat-ID": activeSessionId } : {}) };
}

function setActiveSessionId(sessionId) {
    if (!sessionId) return;
    activeSessionId = sessionId;
    try { sessionStorage.setItem(tabChatStorageKey, sessionId); } catch {}
}

function queueChatNavigation(action) {
    const version = ++chatViewVersion;
    chatViewAbort.abort();
    chatViewAbort = new AbortController();
    const task = chatNavigationTail.then(async () => {
        if (version !== chatViewVersion) return false;
        return action(version);
    }).catch(error => {
        if (version === chatViewVersion) showWarning(error.message || "Could not open that chat.");
        return false;
    });
    chatNavigationTail = task;
    return task;
}

async function ensureConversationReady() {
    let pending;
    do {
        pending = chatNavigationTail;
        await pending;
    } while (pending !== chatNavigationTail);
    if (!activeSessionId || !chatHistoryReady) {
        showWarning("This chat could not load. Refresh or start a new chat before sending.");
        return false;
    }
    return true;
}

function openTutor() {
    window.location.hash = "tutor";
    syncHomeRoute(true);
}

function syncHomeRoute(moveFocus = false) {
    if (!document.getElementById("homePage")) return;
    const wasHome = document.body.classList.contains("home-active");
    const isHome = window.location.hash !== "#tutor";
    document.body.classList.toggle("home-active", isHome);
    if (wasHome && !isHome) window.scrollTo(0, 0);
    requestAnimationFrame(() => {
        updateComposerClearance();
        if (!moveFocus || wasHome === isHome || document.body.classList.contains("home-active") !== isHome) return;
        if (isHome) document.querySelector(".home-actions [data-start-tutor]")?.focus({ preventScroll: true });
        else userInput?.focus({ preventScroll: true });
    });
}

window.addEventListener("hashchange", () => syncHomeRoute(true));
window.addEventListener("pageshow", () => syncHomeRoute());

startTutorButtons.forEach(button => {
    button.addEventListener("click", openTutor);
});

startScienceButtons.forEach(button => {
    button.addEventListener("click", () => {
        window.location.href = "/science";
    });
});

syncHomeRoute();

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
                    <p class="ai-settings-kicker">Delphic AI</p>
                    <h2 id="aiSettingsTitle">Settings</h2>
                </div>
                <button class="ai-settings-close" type="button" data-ai-settings-close aria-label="Close AI settings" title="Close"><svg class="tool-icon" aria-hidden="true"><use href="/static/vendor/lucide/sidebar.svg#x"></use></svg></button>
            </div>
            <div id="workspacePreferencesSlot"></div>
            <form id="aiSettingsForm" class="ai-settings-form">
                <h3 class="ai-settings-section-title">AI connection</h3>

                <div class="ai-connection-status" id="aiConnectionStatus" role="status" hidden>
                    <span class="ai-connection-dot" aria-hidden="true"></span>
                    <span>
                        <strong>Configured</strong>
                        <small id="aiConnectionDetail"></small>
                    </span>
                </div>

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
                    <option value="openrouter">OpenRouter</option>
                </select>

                <label for="aiModelSelect">Tutor model</label>
                <select id="aiModelSelect" name="model"></select>

                <div class="ai-image-model-field" id="aiImageModelField" hidden>
                    <label for="aiImageModelSelect">Image quality</label>
                    <select id="aiImageModelSelect" name="image_model"></select>
                    <p>Images are created through OpenRouter. Terra checks the finished image.</p>
                </div>

                <div class="ai-key-entry" id="aiKeyEntry">
                    <label for="aiApiKeyInput">API key for this provider</label>
                    <div class="ai-key-input-wrap">
                        <input id="aiApiKeyInput" name="api_key" type="password" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="Paste API key" />
                        <button id="toggleApiKeyVisibility" class="ai-key-visibility-btn" type="button" aria-label="Show API key" aria-pressed="false" title="Show API key">
                            <svg class="ai-key-eye" aria-hidden="true"><use href="/static/vendor/lucide/sidebar.svg#eye"></use></svg>
                            <svg class="ai-key-eye-off" aria-hidden="true"><use href="/static/vendor/lucide/sidebar.svg#eye-off"></use></svg>
                        </button>
                    </div>
                </div>

                <div id="aiRememberKeyField" hidden>
                    <label class="ai-remember-key" for="aiRememberKey">
                        <input id="aiRememberKey" type="checkbox" />
                        <span>Remember key on this device</span>
                    </label>
                </div>

                <p class="ai-settings-help" id="aiSettingsHelp">
                    The key stays in server memory while Delphic is running. It is not saved in this browser.
                </p>

                <p class="ai-settings-message" id="aiSettingsMessage" hidden></p>

                <div class="ai-settings-actions">
                    <button class="forget-settings-btn" id="forgetAiKeyBtn" type="button" hidden>Forget API key</button>
                    <button class="secondary-settings-btn" id="replaceAiKeyBtn" type="button" hidden>Replace API key</button>
                    <button class="secondary-settings-btn" type="button" data-ai-settings-close>Not now</button>
                    <button class="primary-settings-btn" id="aiSettingsSubmitBtn" type="submit">Connect</button>
                </div>
            </form>
        </section>
    `;
    document.body.appendChild(dialog);
    const preferences = document.getElementById("workspaceSettingsControls");
    dialog.querySelector("#workspacePreferencesSlot").appendChild(preferences);
    preferences.hidden = false;
    return dialog;
}

const aiSettingsModal = createAiSettingsDialog();
const aiSettingsForm = document.getElementById("aiSettingsForm");
const aiProviderSelect = document.getElementById("aiProviderSelect");
const aiApiKeyInput = document.getElementById("aiApiKeyInput");
const aiModelSelect = document.getElementById("aiModelSelect");
const aiImageModelField = document.getElementById("aiImageModelField");
const aiImageModelSelect = document.getElementById("aiImageModelSelect");
const aiKeyEntry = document.getElementById("aiKeyEntry");
const toggleApiKeyVisibility = document.getElementById("toggleApiKeyVisibility");
const aiConnectionStatus = document.getElementById("aiConnectionStatus");
const aiConnectionDetail = document.getElementById("aiConnectionDetail");
const aiSettingsHelp = document.getElementById("aiSettingsHelp");
const aiSettingsMessage = document.getElementById("aiSettingsMessage");
const forgetAiKeyBtn = document.getElementById("forgetAiKeyBtn");
const replaceAiKeyBtn = document.getElementById("replaceAiKeyBtn");
const aiSettingsSubmitBtn = document.getElementById("aiSettingsSubmitBtn");
const aiSettingsTitle = document.getElementById("aiSettingsTitle");
const aiRememberKey = document.getElementById("aiRememberKey");
const aiRememberKeyField = document.getElementById("aiRememberKeyField");

function announceAiSettingsChange(type) {
    const event = { type, sender: aiSettingsTabId, sentAt: Date.now() };
    if (aiSettingsChannel) {
        aiSettingsChannel.postMessage(event);
        return;
    }
    try {
        localStorage.setItem(aiSettingsEventKey, JSON.stringify(event));
        localStorage.removeItem(aiSettingsEventKey);
    } catch (error) {
        // BroadcastChannel remains the primary cross-tab path.
    }
}

function getAiProviderLabel(providerId) {
    const provider = (aiSettingsStatus.providers || []).find(item => item.id === providerId);
    return provider ? provider.label : "AI";
}

function getModelsForProvider(providerId) {
    const provider = (aiSettingsStatus.providers || []).find(item => item.id === providerId);
    if (Array.isArray(provider?.models) && provider.models.length > 0) {
        return provider.models;
    }
    return fallbackModelsByProvider[providerId] || [];
}

function renderModelOptions(providerId, selectedModel = "") {
    const models = getModelsForProvider(providerId);
    const activeModel = models.some(model => model.id === selectedModel)
        ? selectedModel
        : models[0]?.id || "";

    aiModelSelect.textContent = "";
    models.forEach(model => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.label;
        option.selected = model.id === activeModel;
        aiModelSelect.appendChild(option);
    });
    aiModelSelect.disabled = models.length === 0;
}

function renderImageModelOptions(selectedModel = "") {
    const models = aiSettingsStatus.image_models.length > 0
        ? aiSettingsStatus.image_models
        : [
            { id: "openai/gpt-image-2.5-sunburst", label: "Best quality - GPT Image 2.5 Sunburst" },
            { id: "openai/gpt-image-2.5-flare", label: "Faster - GPT Image 2.5 Flare" },
        ];
    const activeModel = models.some(model => model.id === selectedModel)
        ? selectedModel
        : models[0].id;
    aiImageModelSelect.textContent = "";
    models.forEach(model => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.label;
        option.selected = model.id === activeModel;
        aiImageModelSelect.appendChild(option);
    });
}

function resetApiKeyVisibility() {
    aiApiKeyInput.type = "password";
    toggleApiKeyVisibility.setAttribute("aria-pressed", "false");
    toggleApiKeyVisibility.setAttribute("aria-label", "Show API key");
    toggleApiKeyVisibility.title = "Show API key";
}

function updateAiSettingsButton() {
    if (!aiSettingsBtn) return;
    const needsKey = aiSettingsStatus.loaded && !aiSettingsStatus.configured;
    document.getElementById("aiSettingsLabel").textContent = needsKey ? "Connect AI" : "Settings";
    aiSettingsBtn.title = needsKey ? "Connect AI and open settings" : "Settings";
    aiSettingsBtn.classList.toggle("needs-key", needsKey);
    aiSettingsBtn.dataset.configured = String(aiSettingsStatus.configured);
    aiSettingsBtn.dataset.loaded = String(aiSettingsStatus.loaded);
}

function updateAiSettingsFormState() {
    const isActiveProvider = aiSettingsStatus.configured
        && aiProviderSelect.value === aiSettingsStatus.provider;
    const replacingKey = isReplacingAiKey || aiApiKeyInput.value.trim() !== "";
    if (forgetAiKeyBtn) {
        forgetAiKeyBtn.hidden = !(aiSettingsStatus.can_forget && (isActiveProvider || aiSettingsStatus.has_saved_key));
        forgetAiKeyBtn.textContent = aiSettingsStatus.has_saved_key ? "Forget saved key" : "Forget API key";
    }
    if (replaceAiKeyBtn) {
        replaceAiKeyBtn.hidden = !isActiveProvider;
        replaceAiKeyBtn.textContent = replacingKey ? "Cancel replacement" : "Replace API key";
    }
    if (aiConnectionStatus) {
        aiConnectionStatus.hidden = !isActiveProvider;
    }
    if (aiConnectionDetail && isActiveProvider) {
        aiConnectionDetail.textContent = `${getAiProviderLabel(aiSettingsStatus.provider)} key configured. Connection not verified.`;
    }
    if (aiKeyEntry) {
        aiKeyEntry.hidden = isActiveProvider && !replacingKey;
    }
    if (aiImageModelField) {
        aiImageModelField.hidden = aiProviderSelect.value !== "openrouter";
    }
    if (aiSettingsTitle) {
        aiSettingsTitle.textContent = "Settings";
    }
    if (aiSettingsSubmitBtn) {
        aiSettingsSubmitBtn.textContent = isActiveProvider ? "Save changes" : "Connect";
    }
    if (!aiSettingsHelp) return;

    aiRememberKeyField.hidden = !aiSettingsStatus.device_storage;
    aiRememberKey.disabled = !aiSettingsStatus.device_storage_available;
    if (aiSettingsStatus.device_storage_error) {
        aiSettingsHelp.textContent = aiSettingsStatus.device_storage_error;
    } else if (aiSettingsStatus.device_storage && !aiSettingsStatus.device_storage_available) {
        aiSettingsHelp.textContent = "Protected storage is unavailable. You can still connect temporarily without saving your key.";
    } else if (aiSettingsStatus.device_storage && aiRememberKey.checked) {
        aiSettingsHelp.textContent = "Personal computers only. Stores one connection in your system vault; the app and provider still use the key.";
    } else if (isActiveProvider && replacingKey) {
        aiSettingsHelp.textContent = "Enter a new key. The old key stays active until you save the replacement.";
    } else if (isActiveProvider) {
        aiSettingsHelp.textContent = "You can change models without entering the key again. Without Remember key, it stays only in memory while Delphic runs.";
    } else {
        aiSettingsHelp.textContent = "The key stays in server memory while Delphic is running. It is not saved in this browser.";
    }
}

function showAiSettingsMessage(message, isError = false) {
    if (!aiSettingsMessage) return;
    aiSettingsMessage.textContent = message;
    aiSettingsMessage.hidden = false;
    aiSettingsMessage.classList.toggle("is-error", isError);
}

function openAiSettings(message = "", options = {}) {
    const blockingOverlay = document.getElementById("studyLibraryDialog").open
        || !document.getElementById("deleteChatModal").hidden;
    if (blockingOverlay) {
        // An asynchronous AI failure must not cover an active note draft or confirmation.
        deferredAiSettingsRequest = { message, options };
        return true;
    }
    if (aiSettingsCloseTimeout) {
        clearTimeout(aiSettingsCloseTimeout);
        aiSettingsCloseTimeout = null;
    }
    if (!aiSettingsModal.hidden) {
        if (message) showAiSettingsMessage(message, options.messageIsError === true);
        return true;
    }
    lastAiSettingsFocus = document.activeElement;
    if (!aiSettingsDraftDirty) syncAiSettingsFields();
    isReplacingAiKey = false;
    aiApiKeyInput.value = "";
    resetApiKeyVisibility();
    updateAiSettingsFormState();
    if (message) showAiSettingsMessage(message, options.messageIsError === true);
    else aiSettingsMessage.hidden = true;
    aiSettingsModal.hidden = false;
    setThemeMenuOpen(false);
    setWorkspaceModalActive(true);
    document.body.classList.add("ai-settings-open");
    if (aiKeyEntry.hidden) aiModelSelect.focus();
    else aiApiKeyInput.focus();
    return true;
}

function closeAiSettings(restoreFocus = true) {
    if (aiSettingsModal.hidden) return;
    if (aiSettingsCloseTimeout) {
        clearTimeout(aiSettingsCloseTimeout);
        aiSettingsCloseTimeout = null;
    }
    aiSettingsModal.hidden = true;
    // Keep provider/model choices for reopening, but never retain an unsaved key.
    setThemeMenuOpen(false);
    setWorkspaceModalActive(false);
    document.body.classList.remove("ai-settings-open");
    isReplacingAiKey = false;
    aiApiKeyInput.value = "";
    resetApiKeyVisibility();
    if (restoreFocus && lastAiSettingsFocus instanceof HTMLElement) {
        lastAiSettingsFocus.focus();
    }
    lastAiSettingsFocus = null;
}

function keepAiSettingsFocusInsideDialog(event) {
    if (event.key !== "Tab" || aiSettingsModal.hidden) return;
    const focusable = Array.from(aiSettingsModal.querySelectorAll(
        "button:not([hidden]):not([disabled]), input:not([disabled]), select:not([disabled])",
    )).filter(element => element.getClientRects().length > 0);
    if (focusable.length === 0) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
}

function applyAiSettingsStatus(data) {
    aiSettingsStatus = {
        configured: data?.configured === true,
        provider: typeof data?.provider === "string" ? data.provider : "groq",
        model: typeof data?.model === "string" ? data.model : "",
        image_model: typeof data?.image_model === "string"
            ? data.image_model
            : "openai/gpt-image-2.5-sunburst",
        image_models: Array.isArray(data?.image_models) ? data.image_models : [],
        source: ["session", "env", "device"].includes(data?.source) ? data.source : null,
        device_storage: data?.device_storage === true,
        device_storage_available: data?.device_storage_available === true,
        device_storage_error: typeof data?.device_storage_error === "string" ? data.device_storage_error : "",
        remember_key: data?.remember_key === true,
        has_saved_key: data?.has_saved_key === true,
        can_forget: data?.can_forget === true,
        providers: Array.isArray(data?.providers) ? data.providers : [],
        loaded: true,
    };
}

async function loadAiSettingsStatus() {
    if (aiSettingsMutationPending) {
        aiSettingsRefreshPending = true;
        return aiSettingsStatus;
    }
    const loadNumber = ++latestAiSettingsLoad;
    const mutationVersion = aiSettingsMutationVersion;
    try {
        const res = await fetch("/ai-settings", { cache: "no-store" });
        if (!res.ok) return null;
        const data = await res.json();
        if (
            loadNumber !== latestAiSettingsLoad
            || mutationVersion !== aiSettingsMutationVersion
        ) {
            return aiSettingsStatus;
        }
        applyAiSettingsStatus(data);
        if (!aiSettingsDraftDirty) syncAiSettingsFields();
        updateAiSettingsButton();
        updateAiSettingsFormState();
        return aiSettingsStatus;
    } catch (err) {
        console.error("[AI SETTINGS] status error:", err);
        return null;
    }
}

function syncAiSettingsFields() {
    if (aiSettingsStatus.providers.length) {
        aiProviderSelect.replaceChildren(...aiSettingsStatus.providers.map(provider => {
            const option = document.createElement("option");
            option.value = provider.id;
            option.textContent = provider.label;
            return option;
        }));
    }
    aiProviderSelect.value = aiSettingsStatus.provider || "groq";
    renderModelOptions(aiProviderSelect.value, aiSettingsStatus.model);
    renderImageModelOptions(aiSettingsStatus.image_model);
    aiRememberKey.checked = aiSettingsStatus.remember_key;
}

function markAiSettingsDraftChanged() {
    aiSettingsDraftDirty = true;
    aiSettingsDraftVersion += 1;
    if (aiSettingsCloseTimeout) {
        clearTimeout(aiSettingsCloseTimeout);
        aiSettingsCloseTimeout = null;
    }
}

aiSettingsForm.addEventListener("input", markAiSettingsDraftChanged);
aiSettingsForm.addEventListener("change", markAiSettingsDraftChanged);

async function ensureAiProviderConfigured() {
    if (!aiSettingsStatus.loaded) await loadAiSettingsStatus();
    if (!aiSettingsStatus.loaded || aiSettingsStatus.configured) return true;

    openAiSettings("Connect AI to send this question.");
    return false;
}

if (aiSettingsBtn) {
    aiSettingsBtn.addEventListener("click", () => openAiSettings());
}

aiProviderSelect.addEventListener("change", () => {
    renderModelOptions(aiProviderSelect.value);
    aiRememberKey.checked = false;
    isReplacingAiKey = false;
    aiApiKeyInput.value = "";
    resetApiKeyVisibility();
    updateAiSettingsFormState();
});

aiRememberKey.addEventListener("change", updateAiSettingsFormState);

replaceAiKeyBtn?.addEventListener("click", () => {
    markAiSettingsDraftChanged();
    isReplacingAiKey = !(isReplacingAiKey || aiApiKeyInput.value.trim());
    aiApiKeyInput.value = "";
    resetApiKeyVisibility();
    updateAiSettingsFormState();
    if (isReplacingAiKey) aiApiKeyInput.focus();
});

toggleApiKeyVisibility?.addEventListener("click", () => {
    const shouldShow = aiApiKeyInput.type === "password";
    aiApiKeyInput.type = shouldShow ? "text" : "password";
    toggleApiKeyVisibility.setAttribute("aria-pressed", String(shouldShow));
    const label = shouldShow ? "Hide API key" : "Show API key";
    toggleApiKeyVisibility.setAttribute("aria-label", label);
    toggleApiKeyVisibility.title = label;
    aiApiKeyInput.focus();
});

aiSettingsModal.addEventListener("click", event => {
    if (event.target.closest("[data-ai-settings-close]")) {
        closeAiSettings();
    }
});

aiSettingsForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (aiSettingsMutationPending) return;
    const provider = aiProviderSelect.value;
    const apiKey = aiApiKeyInput.value.trim();
    const model = aiModelSelect.value;
    const imageModel = aiImageModelSelect.value;
    const canReuseKey = aiSettingsStatus.configured && provider === aiSettingsStatus.provider;
    if (!apiKey && !canReuseKey) {
        showAiSettingsMessage("Paste an API key for the selected provider.", true);
        return;
    }
    if (!model) {
        showAiSettingsMessage("Choose a model first.", true);
        return;
    }

    const draftVersion = aiSettingsDraftVersion;
    aiSettingsMutationPending = true;
    aiSettingsMutationVersion += 1;
    aiSettingsSubmitBtn.disabled = true;
    forgetAiKeyBtn.disabled = true;
    try {
        const res = await fetch("/ai-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider,
                api_key: apiKey,
                model,
                image_model: imageModel,
                ...(aiSettingsStatus.device_storage ? { remember_key: aiRememberKey.checked } : {}),
            }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
            showAiSettingsMessage(data?.error || "Could not save AI settings.", true);
            return;
        }
        aiSettingsMutationVersion += 1;
        applyAiSettingsStatus(data);
        updateAiSettingsButton();
        announceAiSettingsChange("saved");
        if (draftVersion !== aiSettingsDraftVersion) {
            updateAiSettingsFormState();
            return;
        }
        aiSettingsDraftDirty = false;
        aiRememberKey.checked = aiSettingsStatus.remember_key;
        isReplacingAiKey = false;
        aiApiKeyInput.value = "";
        resetApiKeyVisibility();
        updateAiSettingsButton();
        updateAiSettingsFormState();
        showAiSettingsMessage("Saved. You can ask the tutor now.");
        aiSettingsCloseTimeout = setTimeout(() => {
            aiSettingsCloseTimeout = null;
            closeAiSettings();
        }, 700);
    } catch (err) {
        showAiSettingsMessage("Network error. Try again.", true);
    } finally {
        aiSettingsMutationPending = false;
        aiSettingsSubmitBtn.disabled = false;
        forgetAiKeyBtn.disabled = false;
        if (aiSettingsRefreshPending) {
            aiSettingsRefreshPending = false;
            loadAiSettingsStatus();
        }
    }
});

forgetAiKeyBtn?.addEventListener("click", async () => {
    if (aiSettingsMutationPending) return;
    if (aiSettingsCloseTimeout) {
        clearTimeout(aiSettingsCloseTimeout);
        aiSettingsCloseTimeout = null;
    }
    forgetAiKeyBtn.disabled = true;
    aiSettingsSubmitBtn.disabled = true;
    aiSettingsMutationPending = true;
    aiSettingsMutationVersion += 1;
    const draftVersion = aiSettingsDraftVersion;
    try {
        const res = await fetch("/ai-settings", { method: "DELETE" });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
            showAiSettingsMessage(data?.error || "Could not forget the API key.", true);
            return;
        }
        aiSettingsMutationVersion += 1;
        applyAiSettingsStatus(data);
        updateAiSettingsButton();
        announceAiSettingsChange("forgotten");
        if (draftVersion !== aiSettingsDraftVersion) {
            updateAiSettingsFormState();
            return;
        }
        aiSettingsDraftDirty = false;
        aiRememberKey.checked = aiSettingsStatus.remember_key;
        isReplacingAiKey = false;
        aiApiKeyInput.value = "";
        resetApiKeyVisibility();
        updateAiSettingsButton();
        updateAiSettingsFormState();
        showAiSettingsMessage(
            aiSettingsStatus.configured
                ? "The temporary key was forgotten. Delphic is using the key from the app's private setup."
                : (aiSettingsStatus.device_storage ? "The saved and temporary API keys were forgotten." : "The temporary API key was forgotten."),
        );
    } catch (error) {
        showAiSettingsMessage("Network error. Try again.", true);
    } finally {
        aiSettingsMutationPending = false;
        forgetAiKeyBtn.disabled = false;
        aiSettingsSubmitBtn.disabled = false;
        if (aiSettingsRefreshPending) {
            aiSettingsRefreshPending = false;
            loadAiSettingsStatus();
        }
    }
});

async function handleAiSettingsTabEvent(event) {
    if (!event || event.sender === aiSettingsTabId) return;
    if (event.type !== "saved" && event.type !== "forgotten") return;

    const status = await loadAiSettingsStatus();
    if (!aiSettingsModal.hidden) {
        if (status?.configured && !aiSettingsDraftDirty) closeAiSettings(false);
        else if (status) showAiSettingsMessage("The saved AI connection changed in another tab. Your draft is still here.");
    }
}

aiSettingsChannel?.addEventListener("message", event => {
    handleAiSettingsTabEvent(event.data);
});

window.addEventListener("storage", event => {
    if (event.key !== aiSettingsEventKey || !event.newValue) return;
    try {
        handleAiSettingsTabEvent(JSON.parse(event.newValue));
    } catch (error) {
        // Ignore malformed coordination messages; no secret data is read here.
    }
});

window.addEventListener("focus", () => {
    loadAiSettingsStatus();
});

window.addEventListener("beforeunload", () => {
    aiSettingsChannel?.close();
});

function createDeleteChatDialog() {
    const dialog = document.createElement("div");
    dialog.className = "delete-chat-modal";
    dialog.id = "deleteChatModal";
    dialog.hidden = true;
    dialog.innerHTML = `
        <div class="delete-chat-backdrop" data-delete-chat-cancel></div>
        <section class="delete-chat-panel" role="alertdialog" aria-modal="true" aria-labelledby="deleteChatTitle" aria-describedby="deleteChatDescription">
            <span class="delete-chat-symbol" aria-hidden="true">!</span>
            <p class="delete-chat-kicker">Remove conversation</p>
            <h2 id="deleteChatTitle">Delete this chat?</h2>
            <p class="delete-chat-preview" id="deleteChatPreview"></p>
            <p class="delete-chat-description" id="deleteChatDescription">This cannot be undone.</p>
            <div class="delete-chat-actions">
                <button class="delete-chat-cancel" type="button" data-delete-chat-cancel>Keep chat</button>
                <button class="delete-chat-confirm" type="button" data-delete-chat-confirm>Delete chat</button>
            </div>
        </section>
    `;
    document.body.appendChild(dialog);
    return dialog;
}

const deleteChatModal = createDeleteChatDialog();
const deleteChatPreview = document.getElementById("deleteChatPreview");
const deleteChatTitle = document.getElementById("deleteChatTitle");
const deleteChatDescription = document.getElementById("deleteChatDescription");
const deleteChatCancelBtn = deleteChatModal.querySelector("[data-delete-chat-cancel]:not(.delete-chat-backdrop)");
const deleteChatConfirmBtn = deleteChatModal.querySelector("[data-delete-chat-confirm]");
let deleteChatResolver = null;
let lastDeleteChatFocus = null;

function resumeDeferredAiSettings() {
    if (!deferredAiSettingsRequest) return;
    const { message, options } = deferredAiSettingsRequest;
    deferredAiSettingsRequest = null;
    openAiSettings(message, options);
}
document.getElementById("studyLibraryDialog").addEventListener("close", resumeDeferredAiSettings);
deleteChatModal.addEventListener("close", resumeDeferredAiSettings);

function closeDeleteChatDialog(shouldDelete = false) {
    if (deleteChatModal.hidden) return;
    deleteChatModal.hidden = true;
    setWorkspaceModalActive(false);
    if (lastDeleteChatFocus?.isConnected) lastDeleteChatFocus.focus();
    lastDeleteChatFocus = null;
    const resolve = deleteChatResolver;
    deleteChatResolver = null;
    resolve?.(shouldDelete);
    deleteChatModal.dispatchEvent(new Event("close"));
}

function confirmSessionDeletion(chatOrChats) {
    if (!aiSettingsModal.hidden || document.getElementById("studyLibraryDialog").open || !deleteChatModal.hidden) {
        return Promise.resolve(false);
    }
    const chats = Array.isArray(chatOrChats) ? chatOrChats : [chatOrChats];
    const isBulkDelete = chats.length > 1;
    deleteChatTitle.textContent = isBulkDelete ? `Delete ${chats.length} chats?` : "Delete this chat?";
    deleteChatPreview.textContent = isBulkDelete
        ? "The selected conversations will be permanently removed."
        : `Delete "${chats[0].preview}"?`;
    deleteChatDescription.textContent = "This cannot be undone.";
    deleteChatCancelBtn.textContent = isBulkDelete ? "Keep chats" : "Keep chat";
    deleteChatConfirmBtn.textContent = isBulkDelete ? `Delete ${chats.length} chats` : "Delete chat";
    lastDeleteChatFocus = sessionActionTrigger || document.activeElement;
    deleteChatModal.hidden = false;
    setWorkspaceModalActive(true);
    deleteChatCancelBtn?.focus();
    return new Promise(resolve => {
        deleteChatResolver = resolve;
    });
}

function keepDeleteChatFocusInsideDialog(event) {
    if (event.key !== "Tab" || deleteChatModal.hidden) return;
    const focusable = Array.from(deleteChatModal.querySelectorAll("button:not([disabled])"));
    if (!focusable.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
    }
}

deleteChatModal.addEventListener("click", event => {
    if (event.target.closest("[data-delete-chat-confirm]")) {
        closeDeleteChatDialog(true);
    } else if (event.target.closest("[data-delete-chat-cancel]")) {
        closeDeleteChatDialog(false);
    }
});

function getTutorWelcomeHtml() {
    return document.getElementById("tutorWelcomeTemplate").innerHTML;
}

function updateTutorEntryLayout() {
    const empty = Boolean(chatMessages.querySelector(".welcome-message"));
    document.getElementById("chatWorkspace").classList.toggle("is-empty", empty);
    document.getElementById("composerStarters").hidden = !empty;
    updateComposerClearance();
}

// Observe only message additions/removals, not streamed answer mutations.
new MutationObserver(updateTutorEntryLayout).observe(chatMessages, { childList: true });
updateTutorEntryLayout();

function removeTutorWelcome() {
    chatMessages.querySelector(".welcome-message")?.remove();
    updateTutorEntryLayout();
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
    light: "Light",
    dark: "Dark",
    neon: "Neon"
};
const neonAccentStorageKey = "delphic-neon-accent";
const neonAccentControls = document.getElementById("neonAccentControls");
const neonAccentName = document.getElementById("neonAccentName");
const neonAccentOptions = Array.from(document.querySelectorAll('input[name="neon-accent"]'));
let selectedNeonAccent = "cyan";

function getSavedNeonAccent() {
    try {
        return localStorage.getItem(neonAccentStorageKey) || "cyan";
    } catch (_error) {
        return selectedNeonAccent;
    }
}

function applyNeonAccent(value) {
    const choice = neonAccentOptions.find(option => option.value === value) || neonAccentOptions[0];
    if (!choice) return;
    selectedNeonAccent = choice.value;
    const root = document.documentElement;
    root.dataset.neonAccent = choice.value;
    root.style.setProperty("--neon-color", choice.dataset.neonColor);
    root.style.setProperty("--neon-text", choice.dataset.neonText);
    root.style.setProperty("--neon-ink", choice.dataset.neonInk);
    neonAccentName.textContent = choice.getAttribute("aria-label");
    neonAccentOptions.forEach(option => { option.checked = option === choice; });
}

neonAccentOptions.forEach(option => {
    option.addEventListener("change", () => {
        if (!option.checked) return;
        applyNeonAccent(option.value);
        try {
            localStorage.setItem(neonAccentStorageKey, option.value);
        } catch (_error) {
            // Keep the selection for this page when browser storage is unavailable.
        }
    });
});

window.addEventListener("storage", event => {
    if (event.key === neonAccentStorageKey || event.key === null) applyNeonAccent(getSavedNeonAccent());
});

function getSavedTheme() {
    const saved = localStorage.getItem("math-tutor-theme") || "dark";
    return themes.includes(saved) ? saved : "dark";
}

function setThemeMenuOpen(isOpen) {
    themeMenu.hidden = !isOpen;
    themeToggle.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) positionToolMenu(themeMenu, themeToggle);
}

function positionToolMenu(menu, trigger, width = trigger.getBoundingClientRect().width) {
    const rect = trigger.getBoundingClientRect();
    menu.style.position = "fixed";
    menu.style.width = `${Math.min(width, innerWidth - 16)}px`;
    menu.style.maxHeight = `${Math.max(44, innerHeight - 16)}px`;
    menu.style.left = "0px";
    menu.style.top = "0px";
    menu.style.bottom = "auto";
    const origin = menu.getBoundingClientRect();
    const left = Math.max(8, Math.min(rect.left, innerWidth - origin.width - 8));
    const below = rect.bottom + 6;
    const preferred = below + origin.height <= innerHeight - 8 ? below : rect.top - origin.height - 6;
    const top = Math.max(8, Math.min(preferred, innerHeight - origin.height - 8));
    // A transformed mobile sidebar is a containing block even for fixed children.
    menu.style.left = `${left - origin.left}px`;
    menu.style.top = `${top - origin.top}px`;
    menu.dataset.anchorTop = String(rect.top);
    menu.dataset.anchorLeft = String(rect.left);
}

function focusToolMenuItem(item, menu) {
    if (!item) return;
    item.focus({ preventScroll: true });
    const itemRect = item.getBoundingClientRect(), menuRect = menu.getBoundingClientRect();
    if (itemRect.top < menuRect.top) menu.scrollTop -= menuRect.top - itemRect.top + 4;
    else if (itemRect.bottom > menuRect.bottom) menu.scrollTop += itemRect.bottom - menuRect.bottom + 4;
}

function getSelectedThemeOption() {
    return Array.from(themeOptions).find(option => option.classList.contains("is-selected")) || themeOptions[0];
}

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    neonAccentControls.hidden = theme !== "neon";
    themeToggle.textContent = themeLabels[theme];
    themeToggle.title = `Current theme: ${theme}.`;
    themeOptions.forEach(option => {
        const isSelected = option.dataset.themeChoice === theme;
        option.classList.toggle("is-selected", isSelected);
        option.setAttribute("aria-checked", String(isSelected));
    });
    rerenderLocalGraphs(theme);
}

function getCurrentTheme() {
    return document.documentElement.getAttribute("data-theme") || "dark";
}

function disposeRenderedGraphs() {
    window.DelphicGraphing?.disposeAllGraphs(chatMessages);
}

function rerenderLocalGraphs(theme = getCurrentTheme()) {
    if (!window.DelphicGraphing) return;
    chatMessages.querySelectorAll(".local-graph-container").forEach(container => {
        if (container.graphSpec) {
            window.DelphicGraphing.renderGraph(container, container.graphSpec, theme);
        }
    });
}

window.addEventListener("delphic-graphing-ready", () => rerenderLocalGraphs());

function loadTheme() {
    applyNeonAccent(getSavedNeonAccent());
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
    setCompetitionMenuOpen(false);
});

document.addEventListener("keydown", event => {
    if (document.getElementById("studyLibraryDialog").open) return;
    keepAiSettingsFocusInsideDialog(event);
    keepDeleteChatFocusInsideDialog(event);

    if (event.key === "Escape" && themeToggle.getAttribute("aria-expanded") === "true") {
        event.preventDefault();
        event.stopImmediatePropagation();
        setThemeMenuOpen(false);
        themeToggle.focus();
        return;
    }

    if (event.key === "Escape" && !aiSettingsModal.hidden) {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeAiSettings();
        return;
    }

    if (event.key === "Escape" && !deleteChatModal.hidden) {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeDeleteChatDialog(false);
        return;
    }

    const isCompetitionMenuOpen = competitionPracticeBtn?.getAttribute("aria-expanded") === "true";
    if (event.key === "Escape" && isCompetitionMenuOpen) {
        setCompetitionMenuOpen(false);
        competitionPracticeBtn.focus();
        return;
    }

    if (event.key === "Escape" && sidebar.classList.contains("open")) {
        setSidebarOpen(false);
        menuBtn.focus();
    }
});

themeToggle.addEventListener("keydown", event => {
    if (event.key === "ArrowDown") {
        event.preventDefault();
        setThemeMenuOpen(true);
        focusToolMenuItem(getSelectedThemeOption(), themeMenu);
    }
});

themeOptions.forEach((option, index) => {
    option.addEventListener("keydown", event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const nextIndex = (index + direction + themeOptions.length) % themeOptions.length;
            focusToolMenuItem(themeOptions[nextIndex], themeMenu);
        }

        if (event.key === "Home") {
            event.preventDefault();
            focusToolMenuItem(themeOptions[0], themeMenu);
        }

        if (event.key === "End") {
            event.preventDefault();
            focusToolMenuItem(themeOptions[themeOptions.length - 1], themeMenu);
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

if (competitionPracticeBtn) {
    competitionPracticeBtn.addEventListener("click", event => {
        event.stopPropagation();
        const isOpen = competitionPracticeBtn.getAttribute("aria-expanded") === "true";
        setCompetitionMenuOpen(!isOpen);
        if (!isOpen) focusToolMenuItem(competitionOptions[0], competitionMenu);
    });

    competitionPracticeBtn.addEventListener("keydown", event => {
        if (event.key === "ArrowDown") {
            event.preventDefault();
            setCompetitionMenuOpen(true);
            focusToolMenuItem(competitionOptions[0], competitionMenu);
        }
    });
}

competitionOptions.forEach((option, index) => {
    option.addEventListener("click", async event => {
        event.stopPropagation();
        setCompetitionMenuOpen(false);
        competitionPracticeBtn?.focus();
        await startCompetitionPractice(option.dataset.competition || "a math competition");
    });

    option.addEventListener("keydown", event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            const direction = event.key === "ArrowDown" ? 1 : -1;
            const nextIndex = (index + direction + competitionOptions.length) % competitionOptions.length;
            focusToolMenuItem(competitionOptions[nextIndex], competitionMenu);
        }

        if (event.key === "Home") {
            event.preventDefault();
            focusToolMenuItem(competitionOptions[0], competitionMenu);
        }

        if (event.key === "End") {
            event.preventDefault();
            focusToolMenuItem(competitionOptions[competitionOptions.length - 1], competitionMenu);
        }

        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            option.click();
        }
    });
});

competitionPicker?.addEventListener("focusout", () => {
    requestAnimationFrame(() => {
        if (!competitionPicker.contains(document.activeElement)) {
            setCompetitionMenuOpen(false);
        }
    });
});

loadTheme();

// ---- Load conversation history on page start ----
async function renderSavedConversation(messages, images = [], target = chatMessages, graphContext = null,
                                       version = chatViewVersion) {
    let pendingGraphRequest = graphContext && isGraphRequest(graphContext) ? graphContext : null;
    const imagesByMessage = new Map();
    const unlinkedImages = [];

    for (const image of images) {
        const messageId = Number(image.message_id);
        if (!Number.isSafeInteger(messageId) || messageId <= 0) {
            unlinkedImages.push(image);
            continue;
        }
        if (!imagesByMessage.has(messageId)) imagesByMessage.set(messageId, []);
        imagesByMessage.get(messageId).push(image);
    }

    for (const message of messages) {
        if (version !== chatViewVersion || !target.isConnected) return;
        const messageImages = imagesByMessage.get(Number(message.id)) || [];
        const messageElement = addMessage(message.role, message.content, {
            ...message,
            generated_image: messageImages.length > 0,
        }, target);
        messageImages.forEach(image => appendGeneratedImage(messageElement, image, target === chatMessages));

        if (message.role === "user") {
            pendingGraphRequest = isGraphRequest(message.content) ? message.content : null;
        } else if (message.role === "assistant" && pendingGraphRequest) {
            await restoreSavedGraph(pendingGraphRequest, target, version);
            pendingGraphRequest = null;
        }
    }

    unlinkedImages.forEach(image => {
        if (version !== chatViewVersion || !target.isConnected) return;
        const messageElement = addMessage(
            "assistant",
            "Here is the saved AI-generated image.",
            { generated_image: true }, target,
        );
        appendGeneratedImage(messageElement, image, target === chatMessages);
    });
}

function updateHistoryPager(data) {
    document.getElementById("loadEarlierMessages")?.remove();
    historyPage = data?.has_more ? data : null;
    if (!historyPage) return;
    const button = document.createElement("button");
    button.id = "loadEarlierMessages";
    button.type = "button";
    button.className = "practice-btn history-more-btn";
    button.textContent = "Load earlier messages";
    button.addEventListener("click", loadEarlierMessages);
    chatMessages.prepend(button);
}

async function loadEarlierMessages() {
    if (!historyPage || loadingEarlierMessages || isSending) return;
    const cursor = historyPage;
    const version = chatViewVersion;
    loadingEarlierMessages = true;
    const button = document.getElementById("loadEarlierMessages");
    if (button) button.disabled = true;
    try {
        const response = await fetch(apiUrl("/sessions/messages"), {
            method: "POST", headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ session_id: cursor.session_id, before_id: cursor.next_before_id, snapshot_id: cursor.snapshot_id }),
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Could not load earlier messages.");
        if (version !== chatViewVersion || activeSessionId !== cursor.session_id) return;
        const height = chatMessages.scrollHeight;
        const top = chatMessages.scrollTop;
        const page = document.createElement("div");
        page.style.display = "contents";
        chatMessages.prepend(page);
        await renderSavedConversation(data.messages, data.images || [], page, data.graph_context, version);
        if (version !== chatViewVersion) {
            window.DelphicGraphing?.disposeAllGraphs(page);
            page.remove();
            return;
        }
        updateHistoryPager(data);
        chatMessages.scrollTop = top + chatMessages.scrollHeight - height;
    } catch (error) {
        showWarning(error.message || "Could not load earlier messages.");
    } finally {
        loadingEarlierMessages = false;
        if (button) button.disabled = false;
    }
}

async function loadHistory() {
    const version = chatViewVersion;
    try {
        let res = await fetch(apiUrl("/history"), {
            headers: getImageRequestHeaders(),
            cache: "no-store",
        });
        if (version !== chatViewVersion) return;
        if (res.status === 404 && activeSessionId) {
            const fresh = await fetch(apiUrl("/sessions/new"), { method: "POST" });
            if (!fresh.ok) throw new Error("Could not start a new chat.");
            const created = await fresh.json();
            if (version !== chatViewVersion) return;
            setActiveSessionId(created.session_id);
            res = await fetch(apiUrl("/history"), { headers: getImageRequestHeaders(), cache: "no-store" });
        }
        if (!res.ok) throw new Error("Could not load this chat. Please refresh and try again.");
        const data = await res.json();
        if (version !== chatViewVersion) return;
        setActiveSessionId(data.session_id);
        if (data.messages && data.messages.length > 0) {
            disposeRenderedGraphs();
            chatMessages.innerHTML = "";
            await renderSavedConversation(data.messages, data.images || [], chatMessages, data.graph_context, version);
        }
        if (version !== chatViewVersion) return;
        chatHistoryReady = true;
        updateHistoryPager(data);
        if (data.tokens_used !== undefined) updateTokenCount(data.tokens_used);
    } catch (e) {
        console.warn("[HISTORY] Could not load history:", e);
    }
}

const initialHistoryLoad = loadHistory();
chatNavigationTail = initialHistoryLoad;

// ---- Session management ----
const newChatBtn = document.getElementById("newChatBtn");
const currentSessionPreview = document.getElementById("currentSessionPreview");
const pastSessionsList = document.getElementById("pastSessionsList");

function updateChatManageActions() {
    const sessionIds = availableSessions.map(chat => chat.session_id);
    const selectedCount = sessionIds.filter(id => selectedSessionIds.has(id)).length;
    const allSelected = sessionIds.length > 0 && selectedCount === sessionIds.length;

    if (chatManageActions) chatManageActions.hidden = !isManagingChats;
    if (deleteSelectedChatsBtn) {
        deleteSelectedChatsBtn.disabled = selectedCount === 0;
        deleteSelectedChatsBtn.textContent = `Delete (${selectedCount})`;
    }
    if (selectAllChatsBtn) {
        selectAllChatsBtn.textContent = allSelected ? "Clear all" : "Select all";
        selectAllChatsBtn.setAttribute("aria-pressed", String(allSelected));
    }
}

function updateSelectedSession(sessionId, isSelected) {
    if (isSelected) selectedSessionIds.add(sessionId);
    else selectedSessionIds.delete(sessionId);
    updateChatManageActions();
}

function setChatManageMode(isActive) {
    isManagingChats = Boolean(isActive && availableSessions.length);
    selectedSessionIds.clear();
    sidebarChats?.classList.toggle("is-managing", isManagingChats);
    if (manageChatsBtn) {
        manageChatsBtn.textContent = isManagingChats ? "Done" : "Manage";
        manageChatsBtn.setAttribute("aria-pressed", String(isManagingChats));
    }
    renderSessions(activeSessionId, availableSessions);
}

function setCompetitionMenuOpen(isOpen) {
    if (!competitionMenu || !competitionPracticeBtn) return;
    competitionMenu.hidden = !isOpen;
    competitionPracticeBtn.setAttribute("aria-expanded", String(isOpen));
    if (isOpen) positionToolMenu(competitionMenu, competitionPracticeBtn);
}

window.addEventListener("workspace-modal-opening", () => {
    setThemeMenuOpen(false);
    setCompetitionMenuOpen(false);
    closeSessionActionMenu();
});
window.addEventListener("resize", () => {
    setThemeMenuOpen(false);
    setCompetitionMenuOpen(false);
});
document.addEventListener("scroll", event => {
    for (const [menu, trigger, close] of [
        [themeMenu, themeToggle, setThemeMenuOpen],
        [competitionMenu, competitionPracticeBtn, setCompetitionMenuOpen],
    ]) {
        if (!menu || menu.hidden || !event.target.contains?.(trigger)) continue;
        const rect = trigger.getBoundingClientRect();
        if (Math.abs(rect.top - Number(menu.dataset.anchorTop)) > 1
            || Math.abs(rect.left - Number(menu.dataset.anchorLeft)) > 1) close(false);
    }
}, true);

function getCompetitionPrompt(competition) {
    return `I want to prepare for ${competition}. Explain what this competition is, who it is usually for, and the main skills it tests. Then give me a beginner-friendly study plan and ask me one question to help me get started. Do not make up dates or deadlines.`;
}

async function loadSessions() {
    const version = chatViewVersion;
    const selected = activeSessionId;
    try {
        const res = await fetch(apiUrl("/sessions"), { headers: getImageRequestHeaders(), cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (version !== chatViewVersion || selected !== activeSessionId) return;
        renderSessions(activeSessionId || data.current_session_id, data.sessions);
        const current = availableSessions.find(chat => chat.session_id === activeSessionId);
        if (current?.title_ready && !current.title_generated && aiSettingsStatus.configured) {
            void summarizeSessionTitle(current.session_id);
        }
    } catch (e) {
        console.warn("[SESSIONS] Could not load sessions:", e);
    }
}

async function summarizeSessionTitle(sessionId) {
    if (requestedSessionTitles.has(sessionId)) return;
    requestedSessionTitles.add(sessionId);
    try {
        const response = await fetch(apiUrl("/sessions/title"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sessionId }),
        });
        if (!response.ok) return;
        const data = await response.json();
        if (!data.title_generated) return;
        // The student may have switched or deleted chats while naming finished.
        const chat = availableSessions.find(item => item.session_id === sessionId);
        if (!chat) return;
        chat.preview = data.title;
        chat.title_generated = true;
        renderSessions(activeSessionId, availableSessions);
        if (activeSessionId === sessionId) updateTokenCount(data.tokens_used);
    } catch (error) {
        console.warn("[SESSIONS] Could not summarize the chat title:", error);
    }
}

function renderSessions(currentId, sessions) {
    availableSessions = Array.isArray(sessions) ? sessions : [];
    const availableIds = new Set(availableSessions.map(chat => chat.session_id));
    for (const selectedId of selectedSessionIds) {
        if (!availableIds.has(selectedId)) selectedSessionIds.delete(selectedId);
    }
    if (isManagingChats && availableSessions.length === 0) isManagingChats = false;
    sidebarChats?.classList.toggle("is-managing", isManagingChats);
    if (manageChatsBtn) {
        manageChatsBtn.hidden = availableSessions.length === 0;
        manageChatsBtn.textContent = isManagingChats ? "Done" : "Manage";
        manageChatsBtn.setAttribute("aria-pressed", String(isManagingChats));
    }
    setActiveSessionId(currentId);
    closeSessionActionMenu();
    const past = availableSessions.filter(s => s.session_id !== currentId);
    const current = availableSessions.find(s => s.session_id === currentId);
    currentSessionDetails = current || null;

    // Update current session preview
    if (currentSessionPreview) {
        currentSessionPreview.textContent = current ? current.preview : "New conversation";
        currentSessionPreview.title = currentSessionPreview.textContent;
    }
    if (currentSessionActionsBtn) {
        currentSessionActionsBtn.hidden = !current || isManagingChats;
        currentSessionActionsBtn.setAttribute(
            "aria-label",
            current ? `More actions for ${current.preview}` : "More actions for this chat"
        );
    }
    if (currentSessionSelect) {
        currentSessionSelect.hidden = !current || !isManagingChats;
        currentSessionSelect.disabled = !current;
        currentSessionSelect.checked = Boolean(current && selectedSessionIds.has(current.session_id));
        currentSessionSelect.value = current?.session_id || "";
        currentSessionSelect.setAttribute(
            "aria-label",
            current ? `Select ${current.preview}` : "Select current chat"
        );
    }
    currentSessionItem?.classList.toggle("is-selectable", Boolean(current && isManagingChats));

    // Render past sessions
    if (!pastSessionsList) return;
    if (past.length === 0) {
        pastSessionsList.innerHTML = `<li class="no-sessions-placeholder">No past sessions yet</li>`;
        updateChatManageActions();
        return;
    }
    pastSessionsList.innerHTML = "";
    past.forEach(s => {
        const li = document.createElement("li");
        li.className = "session-list-item";

        if (isManagingChats) {
            const label = document.createElement("label");
            label.className = "session-select-label";
            label.title = s.preview;

            const checkbox = document.createElement("input");
            checkbox.className = "session-select-checkbox";
            checkbox.type = "checkbox";
            checkbox.value = s.session_id;
            checkbox.checked = selectedSessionIds.has(s.session_id);
            checkbox.setAttribute("aria-label", `Select ${s.preview}`);
            checkbox.addEventListener("change", () => updateSelectedSession(s.session_id, checkbox.checked));

            const preview = document.createElement("span");
            preview.className = "session-preview";
            preview.textContent = s.preview;
            label.append(checkbox, preview);
            li.appendChild(label);
            pastSessionsList.appendChild(li);
            return;
        }

        const openButton = document.createElement("button");
        openButton.className = "session-open-btn";
        openButton.type = "button";
        openButton.title = s.preview;
        const preview = document.createElement("div");
        preview.classList.add("session-preview");
        preview.textContent = s.preview;
        const chatIcon = currentSessionItem?.querySelector(".session-dot")?.cloneNode(true);
        if (chatIcon) {
            chatIcon.classList.remove("active", "session-dot");
            openButton.appendChild(chatIcon);
        }
        openButton.appendChild(preview);

        openButton.addEventListener("click", () => switchToSession(s.session_id));

        const actionsButton = document.createElement("button");
        actionsButton.className = "session-actions-trigger";
        actionsButton.type = "button";
        actionsButton.textContent = "...";
        actionsButton.setAttribute("aria-label", `More actions for ${s.preview}`);
        actionsButton.setAttribute("aria-haspopup", "menu");
        actionsButton.setAttribute("aria-expanded", "false");
        actionsButton.addEventListener("click", event => {
            event.stopPropagation();
            openSessionActionMenu(s, actionsButton);
        });

        li.append(openButton, actionsButton);
        pastSessionsList.appendChild(li);
    });
    updateChatManageActions();
}

async function deleteSelectedSessions() {
    if (isSending) return showWarning("Please wait for the current answer to finish.");
    const selectedChats = availableSessions.filter(chat => selectedSessionIds.has(chat.session_id));
    if (selectedChats.length === 0) return;
    const shouldDelete = await confirmSessionDeletion(selectedChats);
    if (!shouldDelete) return;

    return queueChatNavigation(async version => {
    const deletingActiveChat = selectedChats.some(
        chat => chat.session_id === currentSessionDetails?.session_id
    );
    deleteSelectedChatsBtn.disabled = true;
    deleteSelectedChatsBtn.textContent = "Deleting...";

    try {
        const response = await fetch(apiUrl("/sessions/delete-many"), {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ session_ids: selectedChats.map(chat => chat.session_id) }),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(data?.error || "Could not delete the selected chats.");

        if (deletingActiveChat) {
            setActiveSessionId(data?.current_session_id);
            disposeRenderedGraphs();
            chatMessages.innerHTML = getTutorWelcomeHtml();
            updateTokenCount(0);
        }
        isManagingChats = false;
        selectedSessionIds.clear();
        await loadSessions();
    } catch (error) {
        console.error("[BULK SESSION DELETE]", error);
        showWarning(error.message || "Could not delete the selected chats.");
        updateChatManageActions();
    }
    });
}

manageChatsBtn?.addEventListener("click", () => setChatManageMode(!isManagingChats));

currentSessionSelect?.addEventListener("change", () => {
    if (!currentSessionDetails) return;
    updateSelectedSession(currentSessionDetails.session_id, currentSessionSelect.checked);
});

selectAllChatsBtn?.addEventListener("click", () => {
    const allSelected = availableSessions.length > 0
        && availableSessions.every(chat => selectedSessionIds.has(chat.session_id));
    selectedSessionIds.clear();
    if (!allSelected) {
        availableSessions.forEach(chat => selectedSessionIds.add(chat.session_id));
    }
    renderSessions(activeSessionId, availableSessions);
});

deleteSelectedChatsBtn?.addEventListener("click", deleteSelectedSessions);

document.addEventListener("keydown", event => {
    if (event.key === "Escape" && isManagingChats && deleteChatModal.hidden) {
        setChatManageMode(false);
        manageChatsBtn?.focus();
    }
});

function closeSessionActionMenu(restoreFocus = false) {
    if (!sessionActionMenu) return;
    const trigger = sessionActionTrigger;
    sessionActionMenu.remove();
    sessionActionMenu = null;
    sessionActionTrigger = null;
    trigger?.setAttribute("aria-expanded", "false");
    trigger?.removeAttribute("aria-controls");
    if (restoreFocus) trigger?.focus();
}

function positionSessionActionMenu() {
    if (!sessionActionMenu || !sessionActionTrigger) return;
    const triggerRect = sessionActionTrigger.getBoundingClientRect();
    const menuWidth = sessionActionMenu.offsetWidth;
    const horizontalPadding = 8;
    const left = Math.min(
        Math.max(horizontalPadding, triggerRect.right - menuWidth),
        window.innerWidth - menuWidth - horizontalPadding
    );

    sessionActionMenu.style.left = `${left}px`;
    const menuHeight = sessionActionMenu.offsetHeight;
    const below = triggerRect.bottom + 6;
    const preferredTop = below + menuHeight <= window.innerHeight - horizontalPadding
        ? below
        : triggerRect.top - menuHeight - 6;
    const top = Math.max(horizontalPadding, Math.min(
        preferredTop,
        window.innerHeight - menuHeight - horizontalPadding
    ));
    sessionActionMenu.style.top = `${top}px`;
}

function moveSessionMenuFocus(event) {
    if (!sessionActionMenu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = Array.from(sessionActionMenu.querySelectorAll('[role="menuitem"]'));
    const activeIndex = items.indexOf(document.activeElement);
    let nextIndex = activeIndex;
    if (event.key === "ArrowDown") nextIndex = (activeIndex + 1 + items.length) % items.length;
    if (event.key === "ArrowUp") nextIndex = (activeIndex - 1 + items.length) % items.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = items.length - 1;
    event.preventDefault();
    items[nextIndex].focus();
}

function openSessionActionMenu(chat, trigger) {
    if (sessionActionTrigger === trigger) {
        closeSessionActionMenu(true);
        return;
    }
    closeSessionActionMenu();

    const menu = document.createElement("div");
    menu.className = "session-action-menu";
    menu.id = `sessionActionMenu-${chat.session_id.replace(/[^a-z0-9_-]/gi, "")}`;
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", `Actions for ${chat.preview}`);

    const downloadButton = document.createElement("button");
    downloadButton.className = "session-action-item";
    downloadButton.type = "button";
    downloadButton.setAttribute("role", "menuitem");
    downloadButton.textContent = "Download chat";
    downloadButton.addEventListener("click", async () => {
        downloadButton.disabled = true;
        downloadButton.textContent = "Preparing...";
        await downloadSessionChat(chat);
        closeSessionActionMenu();
    });

    const deleteButton = document.createElement("button");
    deleteButton.className = "session-action-item is-danger";
    deleteButton.type = "button";
    deleteButton.setAttribute("role", "menuitem");
    deleteButton.textContent = "Delete chat";
    deleteButton.addEventListener("click", async () => {
        deleteButton.disabled = true;
        const didDelete = await deleteSessionChat(chat);
        closeSessionActionMenu(!didDelete);
    });

    const heading = document.createElement("div");
    heading.className = "session-action-heading";
    heading.textContent = chat.preview;
    menu.append(heading, downloadButton, deleteButton);
    document.body.appendChild(menu);
    sessionActionMenu = menu;
    sessionActionTrigger = trigger;
    trigger.setAttribute("aria-expanded", "true");
    trigger.setAttribute("aria-controls", menu.id);
    positionSessionActionMenu();
    downloadButton.focus();
}

async function downloadSessionChat(chat, embedLimitBytes = 8 * 1024 * 1024) {
    try {
        const { messages, images } = await loadCompleteTranscript(chat.session_id);
        if (messages.length === 0) {
            showWarning("There is no chat to download yet.");
            return;
        }

        const exportDate = formatExportDate();
        const assets = await loadTranscriptImageAssets(images);
        let filename;
        if (assets.totalBytes <= embedLimitBytes) {
            filename = `delphic-${tutorMode}-chat-${exportDate}.html`;
            const embeddedSources = new Map();
            for (const asset of assets.items) {
                embeddedSources.set(asset.image.id, await blobToDataUrl(asset.blob));
            }
            downloadFile(
                filename,
                buildTranscriptHtml(messages, images, embeddedSources),
                "text/html;charset=utf-8",
            );
        } else {
            filename = `delphic-${tutorMode}-chat-${exportDate}.zip`;
            const relativeSources = new Map();
            const files = [];
            assets.items.forEach((asset, index) => {
                const path = `images/generated-image-${index + 1}.png`;
                relativeSources.set(asset.image.id, path);
                files.push({ name: path, data: asset.bytes });
            });
            const transcript = buildTranscriptHtml(messages, images, relativeSources);
            files.unshift({
                name: "delphic-chat.html",
                data: new TextEncoder().encode(transcript),
            });
            downloadBlob(filename, createZipBlob(files));
        }
        showDownloadHelp(filename);
    } catch (error) {
        console.error("[SESSION DOWNLOAD]", error);
        showWarning(error.message || "Could not download that chat.");
    }
}

async function loadCompleteTranscript(sessionId) {
    let messages = [];
    const images = new Map();
    let cursor = { session_id: sessionId };
    let count = null;
    let textBytes = 0;
    for (;;) {
        const response = await fetch(apiUrl("/sessions/messages"), {
            method: "POST", headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify(cursor),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(data?.error || "Could not download that chat.");
        if (count === null && Number.isInteger(data.total_messages)) count = data.total_messages;
        const page = data.messages || [];
        textBytes += new TextEncoder().encode(JSON.stringify(page)).byteLength;
        if ((count ?? 0) > MAX_TRANSCRIPT_MESSAGES || messages.length + page.length > MAX_TRANSCRIPT_MESSAGES
                || textBytes > MAX_TRANSCRIPT_TEXT_BYTES) {
            throw new Error("This chat exceeds the download limit (10,000 messages or 32 MiB of text). No partial file was downloaded.");
        }
        messages = page.concat(messages);
        (data.images || []).forEach(image => images.set(image.id, image));
        if (!data.has_more) break;
        if (!page.length || !Number.isSafeInteger(data.next_before_id)
                || (cursor.before_id && data.next_before_id >= cursor.before_id)) {
            throw new Error("The chat changed during download. Please try again; no partial file was downloaded.");
        }
        cursor = { session_id: sessionId, before_id: data.next_before_id, snapshot_id: data.snapshot_id };
    }
    if (count !== null && messages.length !== count) {
        throw new Error("The chat changed during download. Please try again; no partial file was downloaded.");
    }
    return { messages, images: [...images.values()] };
}

async function deleteSessionChat(chat) {
    if (isSending) return showWarning("Please wait for the current answer to finish.");
    const shouldDelete = await confirmSessionDeletion(chat);
    if (!shouldDelete) return false;
    return queueChatNavigation(async version => {
    const deletingActiveChat = chat.session_id === currentSessionDetails?.session_id;

    try {
        const response = await fetch(apiUrl("/sessions/delete"), {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ session_id: chat.session_id }),
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(data?.error || "Could not delete that chat.");

        if (deletingActiveChat) {
            setActiveSessionId(data.current_session_id);
            disposeRenderedGraphs();
            chatMessages.innerHTML = getTutorWelcomeHtml();
            updateTokenCount(0);
        }
        await loadSessions();
        return true;
    } catch (error) {
        console.error("[SESSION DELETE]", error);
        showWarning(error.message || "Could not delete that chat.");
        return false;
    }
    });
}

if (currentSessionActionsBtn) {
    currentSessionActionsBtn.addEventListener("click", event => {
        event.stopPropagation();
        if (currentSessionDetails) openSessionActionMenu(currentSessionDetails, currentSessionActionsBtn);
    });
}

document.addEventListener("click", event => {
    if (!sessionActionMenu) return;
    if (event.target.closest("#deleteChatModal")) return;
    if (!sessionActionMenu.contains(event.target) && event.target !== sessionActionTrigger) {
        closeSessionActionMenu();
    }
});

document.addEventListener("keydown", event => {
    if (!sessionActionMenu) return;
    if (!deleteChatModal.hidden) return;
    if (event.key === "Escape") {
        event.preventDefault();
        closeSessionActionMenu(true);
        return;
    }
    moveSessionMenuFocus(event);
});

window.addEventListener("resize", () => closeSessionActionMenu());
window.addEventListener("scroll", positionSessionActionMenu, true);

async function switchToSession(sessionId) {
    if (isSending) return showWarning("Please wait for the current answer to finish.");
    return queueChatNavigation(async version => {
    try {
        const res = await fetch(apiUrl("/sessions/switch"), {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ session_id: sessionId })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not switch chats.");
        if (version !== chatViewVersion) return false;
        window.DelphicAttachments?.clear();
        setActiveSessionId(data.session_id || sessionId);
        chatHistoryReady = false;
        // Reload chat with that session's messages
        disposeRenderedGraphs();
        chatMessages.innerHTML = "";
        if (data.messages && data.messages.length > 0) {
            await renderSavedConversation(data.messages, data.images || [], chatMessages, data.graph_context, version);
        } else {
            chatMessages.innerHTML = getTutorWelcomeHtml();
        }
        if (version !== chatViewVersion) return false;
        chatHistoryReady = true;
        updateHistoryPager(data);
        if (data.tokens_used !== undefined) updateTokenCount(data.tokens_used);
        await loadSessions();
        setSidebarOpen(false);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    } catch (e) {
        console.warn("[SESSIONS] Switch failed:", e);
        showWarning(e.message || "Could not switch chats.");
    }
    });
}

async function startNewChat() {
    if (isSending) return showWarning("Please wait for the current answer to finish.");
    return queueChatNavigation(async version => {
        const res = await fetch(apiUrl("/sessions/new"), { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not start a new chat.");
        if (version !== chatViewVersion) return false;
        window.DelphicAttachments?.clear();
        setActiveSessionId(data.session_id);
        chatHistoryReady = true;
        disposeRenderedGraphs();
        chatMessages.innerHTML = getTutorWelcomeHtml();
        updateHistoryPager(null);
        updateTokenCount(0);
        await loadSessions();
        setSidebarOpen(false);
        return true;
    });
}

if (newChatBtn) {
    newChatBtn.addEventListener("click", startNewChat);
}

async function startCompetitionPractice(competition) {
    if (isSending) {
        showWarning("Please wait for the current answer to finish.");
        return;
    }

    try {
        if (!await startNewChat()) return;
        await sendMessage(getCompetitionPrompt(competition));
    } catch (e) {
        console.warn("[COMPETITION PRACTICE] Could not start a new session:", e);
        showWarning("Could not start competition practice. Please try again.");
    }
}

initialHistoryLoad.then(() => loadSessions());


function setSidebarOpen(isOpen) {
    sidebar.classList.toggle("open", isOpen);
    menuBtn.setAttribute("aria-expanded", String(isOpen));
    menuBtn.setAttribute("aria-label", isOpen ? "Close sidebar" : "Open sidebar");
    menuBtn.title = isOpen ? "Close sidebar" : "Open sidebar";
}

menuBtn.addEventListener("click", () => setSidebarOpen(!sidebar.classList.contains("open")));
document.addEventListener("click", (e) => {
    if (
        sidebar.classList.contains("open") &&
        !sidebar.contains(e.target) &&
        !menuBtn.contains(e.target)
    ) {
        setSidebarOpen(false);
    }
});

window.addEventListener("resize", () => {
    if (window.innerWidth > 768) {
        setSidebarOpen(false);
        setThemeMenuOpen(false);
        loadSidebarWidth();
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
            trust: false,
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
    return wrapMessageTables(sanitizeRenderedHtml(renderMarkdown(text)));
}

function wrapMessageTables(html) {
    const template = document.createElement("template");
    template.innerHTML = html;
    template.content.querySelectorAll("table").forEach(table => {
        const scroller = document.createElement("div");
        scroller.className = "message-table-scroll";
        scroller.tabIndex = 0;
        scroller.setAttribute("role", "region");
        scroller.setAttribute("aria-label", "Table");
        table.replaceWith(scroller);
        scroller.appendChild(table);
    });
    return template.innerHTML;
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
    setResponseActionLabel(practiceBtn, practiceButtonLabel, "pencil-line");
    practiceBtn.addEventListener("click", () => requestPracticeProblem(practiceBtn));
    return practiceBtn;
}

function setResponseActionLabel(button, label, icon) {
    if (icon) {
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("viewBox", "0 0 24 24");
        svg.setAttribute("aria-hidden", "true");
        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttribute("href", `/static/vendor/lucide/sidebar.svg#${icon}`);
        svg.appendChild(use);
        const text = document.createElement("span");
        text.className = "action-label";
        button.replaceChildren(svg, text);
    }
    button.querySelector(".action-label").textContent = label;
}

function createMessageRole(role) {
    const label = document.createElement("div");
    label.className = "message-role";
    label.textContent = role === "assistant" ? "Delphic AI" : "You";
    return label;
}

function createResponseActions(messageElement) {
    const actions = document.createElement("div");
    actions.className = "response-actions";
    const copyBtn = document.createElement("button");
    copyBtn.className = "copy-btn";
    copyBtn.type = "button";
    const setCopyState = copied => {
        const label = copied ? "Copied" : "Copy response";
        setResponseActionLabel(copyBtn, label, copied ? "check" : "copy");
        copyBtn.setAttribute("aria-label", label);
        copyBtn.title = label;
        copyBtn.classList.toggle("copied", copied);
    };
    setCopyState(false);
    copyBtn.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(extractConfidence(messageElement.dataset.rawContent || "").cleanText);
            setCopyState(true);
            setTimeout(() => setCopyState(false), 2000);
        } catch {
            showWarning("Could not copy this response. Please select the answer text and copy it.");
        }
    });
    actions.appendChild(copyBtn);
    messageElement.appendChild(actions);
    return { actions, copyBtn };
}

function updateAssistantMessageContent(messageElement, content) {
    const contentDiv = messageElement.querySelector(".message-content");
    if (!contentDiv) return;

    const { cleanText, level } = extractConfidence(content);
    contentDiv.innerHTML = renderSafeMarkdown(cleanText);
    const badge = createConfidenceBadge(level);
    if (badge) contentDiv.appendChild(badge);

    const timeEl = document.createElement("span");
    timeEl.classList.add("message-time");
    timeEl.textContent = getTimestamp();
    contentDiv.appendChild(timeEl);
    messageElement.dataset.rawContent = content;
    renderMath(contentDiv);
}

function applyResponseMetadata(messageElement, metadata = {}) {
    const finishReason = metadata.finish_reason || "unknown";
    const continuationCount = Number.parseInt(metadata.continuation_count, 10) || 0;
    const messageId = Number.parseInt(metadata.message_id ?? metadata.id, 10);
    const sessionId = metadata.session_id || activeSessionId || "";

    messageElement.dataset.finishReason = finishReason;
    messageElement.dataset.continuationCount = String(continuationCount);
    if (!Number.isNaN(messageId)) messageElement.dataset.messageId = String(messageId);
    if (sessionId) messageElement.dataset.sessionId = sessionId;

    messageElement.querySelector(".continue-response-btn")?.remove();
    messageElement.querySelector(".response-status")?.remove();
    messageElement.querySelector(".science-diagram")?.remove();
    messageElement.querySelector(".study-reference")?.remove();
    if (Array.isArray(metadata.sources) && metadata.sources.length) {
        const references = document.createElement("details");
        references.className = "study-reference";
        const summary = document.createElement("summary");
        summary.textContent = "Matching notes (" + Math.min(metadata.sources.length, 3) + ")";
        references.appendChild(summary);
        metadata.sources.slice(0, 3).forEach(source => {
            const heading = document.createElement("strong");
            heading.textContent = String(source.title || "Study note");
            const quote = document.createElement("blockquote");
            quote.textContent = String(source.excerpt || "");
            references.append(heading, quote);
        });
        messageElement.insertBefore(references, messageElement.querySelector(".response-actions"));
    }

    if (isScienceMode && metadata.diagram && window.DelphicScienceDiagrams) {
        const diagram = window.DelphicScienceDiagrams.createFigure(metadata.diagram);
        if (diagram) {
            messageElement.insertBefore(diagram, messageElement.querySelector(".response-actions"));
        }
    }


    const canContinue = (
        finishReason === "length"
        && metadata.can_continue === true
        && continuationCount < maxContinuationsPerAnswer
        && !Number.isNaN(messageId)
        && Boolean(sessionId)
    );
    if (canContinue) {
        const continueBtn = document.createElement("button");
        continueBtn.className = "continue-response-btn";
        continueBtn.type = "button";
        setResponseActionLabel(continueBtn, "Continue response", "arrow-down");
        continueBtn.addEventListener("click", () => requestResponseContinuation(continueBtn));
        messageElement.querySelector(".response-actions").appendChild(continueBtn);
        return;
    }

    if (finishReason === "error") {
        const status = document.createElement("span");
        status.className = "response-status";
        status.setAttribute("role", "status");
        status.textContent = "Response interrupted. Please try again.";
        messageElement.querySelector(".response-actions").appendChild(status);
    } else if (continuationCount > 0) {
        const status = document.createElement("span");
        status.className = "response-status";
        status.setAttribute("role", "status");
        status.textContent = finishReason === "complete"
            ? "Response completed"
            : finishReason === "length"
                ? "Response reached its limit"
                : "Response continued";
        messageElement.querySelector(".response-actions").appendChild(status);
    }
}

async function requestResponseContinuation(button) {
    if (!await ensureConversationReady()) return;
    const messageElement = button.closest(".message.assistant");
    if (!messageElement?.isConnected || isSending) return;

    const messageId = Number.parseInt(messageElement.dataset.messageId, 10);
    const sessionId = messageElement.dataset.sessionId || activeSessionId;
    if (Number.isNaN(messageId) || !sessionId) {
        showWarning("Refresh this chat before continuing the response.");
        return;
    }

    isSending = true;
    button.disabled = true;
    setResponseActionLabel(button, "Continuing...");
    try {
        const res = await fetch(apiUrl("/responses/continue"), {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ message_id: messageId, session_id: sessionId }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) {
            throw new Error(data?.error || "The response could not continue. Please try again.");
        }

        updateAssistantMessageContent(messageElement, data.reply || "");
        applyResponseMetadata(messageElement, data);
        if (data.tokens_used !== undefined) updateTokenCount(data.tokens_used);
        await loadSessions();
        scrollToBottom();
    } catch (error) {
        button.disabled = false;
        setResponseActionLabel(button, "Retry continuation");
        showWarning(error.message || "The response could not continue. Please try again.");
    } finally {
        isSending = false;
        userInput.focus();
    }
}

function addMessage(role, content, metadata = {}, target = chatMessages) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", role);
    if (metadata.generated_image) msgDiv.classList.add("generated-image-message");

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");

    if (role === "assistant") {
        msgDiv.dataset.rawContent = content;
        const { cleanText, level } = extractConfidence(content);
        contentDiv.innerHTML = renderSafeMarkdown(cleanText);
        const badge = createConfidenceBadge(level);
        if (badge) contentDiv.appendChild(badge);
    } else {
        contentDiv.textContent = content;
        if (metadata.attachments?.length) {
            const names = document.createElement("div");
            names.className = "message-attachments";
            names.textContent = metadata.attachments.map(item => item.name).join(" | ");
            contentDiv.appendChild(names);
        }
    }

    // Timestamp
    const timeEl = document.createElement("span");
    timeEl.classList.add("message-time");
    timeEl.textContent = getTimestamp();
    contentDiv.appendChild(timeEl);

    msgDiv.append(createMessageRole(role), contentDiv);

    // Add copy button for assistant messages
    if (role === "assistant") {
        const { actions } = createResponseActions(msgDiv);
        if (!metadata.generated_image) actions.appendChild(createPracticeButton());
        applyResponseMetadata(msgDiv, metadata);
    }

    target.appendChild(msgDiv);

    // Render LaTeX after DOM insertion
    if (role === "assistant") {
        renderMath(contentDiv);
    }

    if (target === chatMessages) scrollToBottom();
    return msgDiv;
}

// ---- Streaming bubble ----
// Creates an empty assistant bubble and returns references to update it live.
function createStreamingBubble() {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");
    msgDiv.setAttribute("aria-busy", "true");

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

    msgDiv.append(createMessageRole("assistant"), contentDiv);

    // Reserve the action row while the response streams.
    const { actions, copyBtn } = createResponseActions(msgDiv);
    copyBtn.style.display = "none"; // hidden until streaming is complete

    chatMessages.appendChild(msgDiv);
    scrollToBottom();

    const practiceBtn = createPracticeButton();
    practiceBtn.style.display = "none";
    actions.appendChild(practiceBtn);

    return { bubble: msgDiv, contentDiv, textEl, copyBtn, practiceBtn };
}

// ---- Typing indicator ----
function showTyping() {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");
    msgDiv.id = "typingIndicator";
    msgDiv.setAttribute("role", "status");

    msgDiv.innerHTML = `
        <div class="typing-indicator" aria-hidden="true">
            <span></span><span></span><span></span>
        </div><span class="thinking-label">Thinking...</span>
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
    window.DelphicAttachments?.setBusy(true);
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="send-spinner"></div>';
}

function hideSpinner() {
    window.DelphicAttachments?.setBusy(false);
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
    if (warningTimeout !== null) window.clearTimeout(warningTimeout);
    warningTimeout = window.setTimeout(() => {
        warning.textContent = "";
        warningTimeout = null;
    }, 30_000);
}

function formatExportDate(date = new Date()) {
    return date.toISOString().slice(0, 19).replace("T", "_").replace(/:/g, "-");
}

function renderTranscriptAssistantBody(content) {
    const container = document.createElement("div");
    container.innerHTML = renderSafeMarkdown(content.trim());
    if (typeof renderMathInElement === "function") {
        renderMathInElement(container, {
            delimiters: [
                { left: "$$", right: "$$", display: true },
                { left: "\\[", right: "\\]", display: true },
                { left: "\\(", right: "\\)", display: false },
                { left: "$", right: "$", display: false },
            ],
            output: "mathml",
            throwOnError: false,
            trust: false,
        });
    }
    return container.innerHTML;
}

function buildTranscriptHtml(messages, images = [], imageSources = new Map()) {
    const exportedAt = new Date().toLocaleString();
    const imagesByMessage = new Map();
    images.forEach(image => {
        const key = Number(image.message_id);
        if (!imagesByMessage.has(key)) imagesByMessage.set(key, []);
        imagesByMessage.get(key).push(image);
    });
    const messageHtml = messages.map((msg) => {
        const role = msg.role === "assistant" ? "Tutor" : "Student";
        const rawContent = String(msg.content || "");
        const content = msg.role === "assistant"
            ? extractConfidence(rawContent).cleanText
            : rawContent;
        const body = msg.role === "assistant"
            ? renderTranscriptAssistantBody(content)
            : `<p>${escapeHtml(content.trim()).replace(/\n/g, "<br>")}</p>`;
        const attachmentNames = Array.isArray(msg.attachments) && msg.attachments.length
            ? `<p>Attachments: ${msg.attachments.map(item => escapeHtml(String(item.name || "file"))).join(" | ")}</p>`
            : "";
        const libraryReferences = Array.isArray(msg.sources) && msg.sources.length
            ? "<details><summary>Matching notes</summary>" + msg.sources.slice(0, 3).map(source =>
                "<p><strong>" + escapeHtml(String(source.title || "Study note")) + "</strong></p><blockquote>"
                + escapeHtml(String(source.excerpt || "")) + "</blockquote>").join("") + "</details>"
            : "";
        const diagram = msg.role === "assistant" && window.DelphicScienceDiagrams
            ? window.DelphicScienceDiagrams.toStaticHtml(msg.diagram)
            : "";

        const generatedImages = (imagesByMessage.get(Number(msg.id)) || []).map(image => {
            const source = imageSources.get(image.id);
            if (!source) return "";
            const prompt = escapeHtml(String(image.prompt || "Student-requested image"));
            return `
                <figure class="generated-image">
                    <img src="${escapeHtml(source)}" alt="AI-generated image: ${prompt}" />
                    <figcaption><strong>AI-generated image</strong><span>${prompt}</span></figcaption>
                </figure>
            `;
        }).join("");

        return `
            <article class="message ${msg.role}">
                <div class="role">${role}</div>
                <div class="bubble">${body}${attachmentNames}${libraryReferences}</div>
                ${diagram}
                ${generatedImages}
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
        .message-table-scroll { max-width: 100%; overflow-x: auto; }
        table { min-width: 100%; border-collapse: collapse; }
        th, td { padding: 8px 12px; border: 1px solid var(--line); text-align: left; }
        .science-diagram {
            margin: 12px 0 0;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--paper);
            padding: 14px;
            break-inside: avoid;
        }
        .science-diagram-title {
            margin: 0 0 8px;
            color: var(--accent);
            font-size: 17px;
        }
        .science-diagram svg {
            display: block;
            width: min(100%, 620px);
            max-height: 470px;
            margin: 0 auto;
        }
        .science-diagram figcaption {
            margin-top: 8px;
            color: var(--muted);
            font-size: 13px;
        }
        .science-diagram-shape {
            fill: #ecfeff;
            stroke: #0f766e;
            stroke-width: 0.8;
        }
        .science-diagram-line {
            fill: none;
            stroke: #0f766e;
            stroke-width: 1.1;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .science-diagram-arrowhead { fill: #0f766e; }
        .science-diagram text {
            fill: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 3.4px;
        }
        .science-diagram-arrow-label { font-size: 3.1px; font-weight: 650; }
        .science-diagram-callout-label { font-size: 3px; font-weight: 650; }
        .generated-image {
            margin: 12px 0 0;
            overflow: hidden;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--paper);
            break-inside: avoid;
        }
        .generated-image img {
            display: block;
            width: 100%;
            max-height: 720px;
            object-fit: contain;
            background: #f1f5f9;
        }
        .generated-image figcaption {
            display: flex;
            flex-direction: column;
            gap: 3px;
            padding: 12px 14px;
            color: var(--muted);
            font-size: 13px;
        }
        .generated-image figcaption strong { color: var(--accent); }
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
    downloadBlob(filename, new Blob([content], { type: mimeType }));
}

function downloadBlob(filename, blob) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    // Give the browser time to begin the file download before releasing the temporary URL.
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function loadTranscriptImageAssets(images) {
    const items = [];
    let totalBytes = 0;
    for (const image of images) {
        if (!image?.id || !image?.url) continue;
        const response = await fetch(image.url, { headers: getImageRequestHeaders() });
        if (!response.ok) throw new Error("Could not include one of this chat's images.");
        const blob = await response.blob();
        if (blob.type !== "image/png") throw new Error("A chat image had an unsupported format.");
        const bytes = new Uint8Array(await blob.arrayBuffer());
        totalBytes += bytes.byteLength;
        if (totalBytes > MAX_TRANSCRIPT_IMAGE_BYTES) throw new Error("This chat exceeds the 64 MiB image download limit. No partial file was downloaded.");
        items.push({ image, blob, bytes });
    }
    return { items, totalBytes };
}

function blobToDataUrl(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.addEventListener("load", () => resolve(String(reader.result)));
        reader.addEventListener("error", () => reject(new Error("Could not prepare a chat image.")));
        reader.readAsDataURL(blob);
    });
}

function crc32(bytes) {
    let crc = 0xffffffff;
    for (const byte of bytes) {
        crc ^= byte;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
        }
    }
    return (crc ^ 0xffffffff) >>> 0;
}

function zipHeader(size) {
    return new Uint8Array(size);
}

function setZipUint16(bytes, offset, value) {
    new DataView(bytes.buffer).setUint16(offset, value, true);
}

function setZipUint32(bytes, offset, value) {
    new DataView(bytes.buffer).setUint32(offset, value, true);
}

function createZipBlob(files) {
    const encoder = new TextEncoder();
    const parts = [];
    const directory = [];
    let offset = 0;

    for (const file of files) {
        const name = encoder.encode(file.name);
        const data = file.data instanceof Uint8Array ? file.data : new Uint8Array(file.data);
        const checksum = crc32(data);
        const local = zipHeader(30);
        setZipUint32(local, 0, 0x04034b50);
        setZipUint16(local, 4, 20);
        setZipUint16(local, 6, 0x0800);
        setZipUint16(local, 8, 0);
        setZipUint32(local, 14, checksum);
        setZipUint32(local, 18, data.byteLength);
        setZipUint32(local, 22, data.byteLength);
        setZipUint16(local, 26, name.byteLength);
        parts.push(local, name, data);

        const central = zipHeader(46);
        setZipUint32(central, 0, 0x02014b50);
        setZipUint16(central, 4, 20);
        setZipUint16(central, 6, 20);
        setZipUint16(central, 8, 0x0800);
        setZipUint16(central, 10, 0);
        setZipUint32(central, 16, checksum);
        setZipUint32(central, 20, data.byteLength);
        setZipUint32(central, 24, data.byteLength);
        setZipUint16(central, 28, name.byteLength);
        setZipUint32(central, 42, offset);
        directory.push(central, name);
        offset += local.byteLength + name.byteLength + data.byteLength;
    }

    const directorySize = directory.reduce((sum, part) => sum + part.byteLength, 0);
    const end = zipHeader(22);
    setZipUint32(end, 0, 0x06054b50);
    setZipUint16(end, 8, files.length);
    setZipUint16(end, 10, files.length);
    setZipUint32(end, 12, directorySize);
    setZipUint32(end, 16, offset);
    return new Blob([...parts, ...directory, end], { type: "application/zip" });
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

async function requestPracticeProblem(button) {
    if (button) {
        button.disabled = true;
        setResponseActionLabel(button, "Making practice...");
    }

    try {
        await sendMessage(practicePrompt, { practiceMode: true });
    } finally {
        if (button) {
            button.disabled = false;
            setResponseActionLabel(button, practiceButtonLabel);
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

// ---- Add a local 2D or 3D graph to the chat ----
function isGraphRequest(text) {
    const hasEquation = /^\s*y\s*=\s*.+/i.test(text)
        || /^\s*f\s*\(\s*x\s*\)\s*=\s*.+/i.test(text)
        || /^\s*z\s*(?:=|\^\s*2\s*=|\u00b2\s*=)/im.test(text)
        || /^\s*r\s*=\s*.+/i.test(text)
        || /^\s*x\s*=.+[,;\n]+\s*y\s*=/im.test(text)
        || /^\s*(?:x|y)\s*(?:\^|\u00b2)/i.test(text)
        || /\bvector\s+field\b/i.test(text);
    if (hasEquation || /\b(plot|graph|chart)\b/i.test(text)) return true;
    if (isSupportedLocalScienceDiagramRequest(text)) return false;
    if (/\b(image|picture|photo|photograph|illustration|visual|diagram|artwork)\b/i.test(text)) return false;
    return /\b(draw|sketch)\b/i.test(text);
}

function addLocalGraph(plotData, target = chatMessages) {
    const msgDiv = document.createElement("div");
    msgDiv.classList.add("message", "assistant");

    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");
    contentDiv.classList.add("graph-card");

    const graphId = "graph-" + Date.now();
    const label = plotData.equation_latex || "";
    const is3dGraph = plotData.kind === "surface_3d" || plotData.kind === "curve_3d";
    const is3dSystem = plotData.kind === "surface_3d" && Number(plotData.surface_count) > 1;
    const title = plotData.kind === "points_2d"
        ? "Interactive point plot"
        : plotData.kind === "curve_3d"
            ? "Interactive 3D curve"
            : plotData.kind === "surface_3d"
            ? is3dSystem ? "Interactive 3D surfaces" : "Interactive 3D surface"
            : plotData.kind === "vector_field_2d"
                ? "Interactive vector field"
                : plotData.kind === "inequality_2d"
                    ? "Interactive shaded region"
                    : plotData.kind === "polar_2d"
                        ? "Interactive polar graph"
                        : plotData.kind === "parametric_2d"
                            ? "Interactive parametric curve"
            : "Interactive 2D graph";
    const header = document.createElement("div");
    header.classList.add("graph-card-header");

    const titleEl = document.createElement("span");
    titleEl.textContent = title;

    const labelEl = document.createElement("strong");
    labelEl.textContent = `\\(${label}\\)`;

    const graphEl = document.createElement("div");
    graphEl.classList.add("local-graph-container");
    graphEl.id = graphId;
    graphEl.graphSpec = plotData;

    const description = document.createElement("p");
    description.className = "graph-description";
    description.textContent = is3dGraph
        ? is3dSystem
            ? "Each equation is shown as a surface on the same axes. Rotate or zoom to inspect where they meet."
            : plotData.kind === "curve_3d"
                ? "Rotate or zoom to inspect the curve in x, y, and z space."
                : "Surface height is measured on the z-axis."
        : plotData.kind === "inequality_2d"
            ? "The tinted area shows every point that makes the inequality true."
            : plotData.kind === "vector_field_2d"
                ? "Each arrow shows the direction and relative strength at that point."
        : "Pan to move around the graph, zoom to inspect it, or reset the view at any time.";

    header.append(titleEl, labelEl);
    contentDiv.append(header, graphEl, description);

    msgDiv.append(createMessageRole("assistant"), contentDiv);
    target.appendChild(msgDiv);

    renderMath(contentDiv);
    const render = () => {
        if (!graphEl.isConnected) return;
        if (window.DelphicGraphing) {
            graphEl.classList.remove("graph-error");
            window.DelphicGraphing.renderGraph(graphEl, plotData, getCurrentTheme());
            return;
        }
        graphEl.textContent = "Your equation is shown above, but the graph renderer could not load.";
        graphEl.classList.add("graph-error");
    };
    if (window.DelphicGraphing) {
        requestAnimationFrame(render);
    } else {
        window.addEventListener("delphic-graphing-ready", render, { once: true });
        window.setTimeout(() => {
            if (!window.DelphicGraphing) render();
        }, 1200);
    }
    if (target === chatMessages) scrollToBottom();
}

async function showPlotResult(plotPromise) {
    try {
        const plotRes = await plotPromise;
        if (!plotRes) return false;
        const plotData = await plotRes.json();
        if (plotRes.ok && plotData.kind) {
            addLocalGraph(plotData);
            return true;
        }
        showWarning(plotData.error || "I could not graph that. Try: y = x^2 - 4.");
    } catch (plotErr) {
        console.error("[PLOT] parse error:", plotErr);
        showWarning("I could not load the graph. Please try a simpler equation.");
    }
    return false;
}

async function restoreSavedGraph(message, target = chatMessages, version = chatViewVersion) {
    try {
        const response = await fetch(apiUrl("/plot"), {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ message, restore_only: true }),
            signal: chatViewAbort.signal,
        });
        const graph = await response.json().catch(() => null);
        if (response.ok && graph?.kind && target.isConnected && version === chatViewVersion) addLocalGraph(graph, target);
    } catch (error) {
        if (error.name === "AbortError") return;
        console.warn("[GRAPH HISTORY] Could not restore saved graph:", error);
    }
}

async function saveLocalGraphMessage(message) {
    const response = await fetch(apiUrl("/local-graph-message"), {
        method: "POST",
        headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ message }),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
        throw new Error(data?.error || "Could not save the graph request.");
    }
    if (data?.tokens_used !== undefined) updateTokenCount(data.tokens_used);
    return data?.reply || "Here is the local graph.";
}

// ---- AI image generation ----
function isImageModeOn() {
    return Boolean(
        imageGenerationEnabled
        && imageModeBtn
        && imageModeBtn.getAttribute("aria-pressed") === "true"
    );
}

function setImageModeActive(isActive) {
    if (!imageModeBtn || !imageModePicker) return;
    imageModeBtn.setAttribute("aria-pressed", String(isActive));
    imageModeBtn.classList.toggle("is-active", isActive);
    imageModePicker.hidden = !isActive;
    const label = imageModeBtn.querySelector("span:last-child");
    if (label) label.textContent = isActive ? "Creating image" : "Create image";
    if (isActive) userInput.focus();
}

function imageModeLabel(mode) {
    return {
        educational_visual: "Educational visual",
        realistic_image: "Realistic image",
        creative_illustration: "Creative illustration",
    }[mode] || "AI image";
}

function createImageAction(label, className = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `generated-image-action ${className}`.trim();
    button.textContent = label;
    return button;
}

async function loadOwnedGeneratedImage(picture, imageUrl) {
    try {
        const response = await fetch(imageUrl, {
            headers: getImageRequestHeaders(),
            cache: "no-store",
        });
        if (!response.ok) throw new Error("Saved image request failed.");
        const blob = await response.blob();
        if (!blob.type.startsWith("image/")) throw new Error("Saved image format was invalid.");

        const objectUrl = URL.createObjectURL(blob);
        picture.addEventListener("load", () => URL.revokeObjectURL(objectUrl), { once: true });
        picture.src = objectUrl;
    } catch (error) {
        // The normal URL still works when the session cookie is already available.
        picture.src = imageUrl;
    }
}

function appendGeneratedImage(messageElement, image, scroll = true) {
    if (!messageElement || !image?.id || !image?.url) return null;
    messageElement.classList.add("generated-image-message");

    const card = document.createElement("figure");
    card.className = "generated-image-card";
    card.dataset.imageId = image.id;
    card.dataset.imagePrompt = String(image.prompt || "");
    card.dataset.mode = String(image.mode || "educational_visual");

    const media = document.createElement("div");
    media.className = "generated-image-media";

    const picture = document.createElement("img");
    const prompt = String(image.prompt || "a student-requested visual").trim();
    picture.alt = `AI-generated ${imageModeLabel(image.mode).toLowerCase()}: ${prompt}`.slice(0, 240);
    picture.width = Number(image.width) || 1024;
    picture.height = Number(image.height) || 1024;
    picture.loading = "lazy";
    picture.addEventListener("load", () => {
        if (scroll && messageElement.isConnected) keepLatestImageAboveComposer();
    }, { once: true });
    loadOwnedGeneratedImage(picture, image.url);

    const badge = document.createElement("span");
    badge.className = "generated-image-label";
    badge.textContent = "AI-generated";
    media.append(picture, badge);

    const caption = document.createElement("figcaption");
    const promptText = document.createElement("p");
    promptText.className = "generated-image-prompt";
    promptText.textContent = prompt;

    const actions = document.createElement("div");
    actions.className = "generated-image-actions";

    const download = document.createElement("a");
    download.className = "generated-image-action";
    download.href = image.download_url || `${image.url}?download=1`;
    download.download = "";
    download.textContent = "Download";

    const edit = createImageAction("Edit prompt");
    edit.addEventListener("click", () => {
        setImageModeActive(true);
        if (imageModeSelect && image.mode) imageModeSelect.value = image.mode;
        userInput.value = prompt;
        userInput.dispatchEvent(new Event("input"));
        userInput.focus();
    });

    const regenerate = createImageAction("Regenerate");
    regenerate.addEventListener("click", () => {
        generateImage(prompt, image.mode || "educational_visual");
    });

    const remove = createImageAction("Delete", "is-danger");
    remove.addEventListener("click", async () => {
        remove.disabled = true;
        remove.textContent = "Deleting...";
        try {
            const response = await fetch(image.url, {
                method: "DELETE",
                headers: getImageRequestHeaders(),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) throw new Error(data?.error || "Could not delete this image.");
            const note = document.createElement("p");
            note.className = "generated-image-deleted";
            note.textContent = "Image deleted";
            card.replaceWith(note);
        } catch (error) {
            remove.disabled = false;
            remove.textContent = "Delete";
            showWarning(error.message || "Could not delete this image.");
        }
    });

    actions.append(download, edit, regenerate, remove);
    caption.append(promptText, actions);
    card.append(media, caption);
    messageElement.appendChild(card);
    if (scroll) keepLatestImageAboveComposer();
    return card;
}

function keepLatestImageAboveComposer() {
    const version = chatViewVersion;
    requestAnimationFrame(() => {
        if (version !== chatViewVersion) return;
        const previousBehavior = chatMessages.style.scrollBehavior;
        chatMessages.style.scrollBehavior = "auto";
        chatMessages.scrollTop = chatMessages.scrollHeight;
        requestAnimationFrame(() => {
            chatMessages.style.scrollBehavior = previousBehavior;
        });
    });
}

function createImageLoadingState(prompt, mode, requestId) {
    const message = document.createElement("div");
    message.className = "message assistant image-generation-message";
    message.dataset.requestId = requestId;

    const status = document.createElement("div");
    status.className = "image-generation-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    const spinner = document.createElement("span");
    spinner.className = "image-generation-spinner";
    spinner.setAttribute("aria-hidden", "true");

    const text = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = `Creating ${imageModeLabel(mode).toLowerCase()}...`;
    const detail = document.createElement("span");
    detail.textContent = "Delphic will check it before showing it.";
    text.append(title, detail);

    const cancel = createImageAction("Cancel");
    status.append(spinner, text, cancel);
    message.appendChild(status);
    chatMessages.appendChild(message);
    scrollToBottom();
    return { message, status, title, detail, cancel, prompt, mode, requestId };
}

function showImageRetryState(state, message, requestId = null) {
    state.status.classList.add("has-error");
    state.status.replaceChildren();
    const text = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = "Image not ready";
    const detail = document.createElement("span");
    detail.textContent = message;
    text.append(title, detail);
    const retry = createImageAction("Retry");
    retry.addEventListener("click", () => {
        state.message.remove();
        generateImage(state.prompt, state.mode, {
            requestId: requestId || crypto.randomUUID(),
            skipUserMessage: true,
        });
    });
    state.status.append(text, retry);
}

async function generateImage(promptOverride = null, modeOverride = null, options = {}) {
    if (!await ensureConversationReady()) return;
    const version = chatViewVersion;
    if (window.DelphicAttachments?.hasFiles()) {
        showWarning("Remove attachments before creating an image. Attachments are for asking about files or photos.");
        return;
    }
    const prompt = String(promptOverride ?? userInput.value).trim();
    const mode = modeOverride || imageModeSelect?.value || "educational_visual";
    if (!prompt) return;
    if (isSending) {
        showWarning("Please wait for the current request to finish.");
        return;
    }
    if (prompt.length < 3) {
        showWarning("Describe the image with a few more words.");
        userInput.focus();
        return;
    }
    if (!await ensureAiProviderConfigured()) return;
    if (version !== chatViewVersion || isSending) return;

    isSending = true;
    const requestId = options.requestId || crypto.randomUUID();
    if (!options.skipUserMessage) {
        removeTutorWelcome();
        addMessage("user", prompt);
    }
    if (promptOverride === null) {
        userInput.value = "";
        userInput.style.height = "auto";
    }
    showSpinner();

    const state = createImageLoadingState(prompt, mode, requestId);
    const controller = new AbortController();
    let cancelled = false;
    state.cancel.addEventListener("click", () => {
        cancelled = true;
        controller.abort();
        showImageRetryState(
            state,
            "You stopped waiting. Retry shortly to check the same request without buying a duplicate.",
            requestId,
        );
    }, { once: true });

    try {
        const response = await fetch("/images/generate", {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({
                prompt,
                mode,
                area: tutorMode,
                request_id: requestId,
            }),
            signal: controller.signal,
        });
        const data = await response.json().catch(() => null);
        if (!response.ok) throw new Error(data?.error || "Delphic could not create that image.");
        if (cancelled || version !== chatViewVersion || !state.message.isConnected) return;

        state.message.remove();
        const assistant = addMessage("assistant", data.message?.content || "Here is the AI-generated image.", {
            ...(data.message || {}),
            generated_image: true,
        });
        appendGeneratedImage(assistant, data.image);
        setImageModeActive(false);
        await loadSessions();
    } catch (error) {
        if (!cancelled && error.name !== "AbortError") {
            showImageRetryState(state, error.message || "Delphic could not create that image.");
            if (/openrouter|api key/i.test(error.message || "")) {
                openAiSettings(error.message, { messageIsError: true });
            }
        }
    } finally {
        hideSpinner();
        isSending = false;
        userInput.focus();
    }
}

if (imageModeBtn) {
    imageModeBtn.addEventListener("click", () => setImageModeActive(!isImageModeOn()));
}

function requestedImageMode(text) {
    if (/\b(realistic|photorealistic|photo|photograph|lifelike)\b/i.test(text)) {
        return "realistic_image";
    }
    if (/\b(creative|artistic|cartoon|storybook|fantasy)\b/i.test(text)) {
        return "creative_illustration";
    }
    return "educational_visual";
}

function isSupportedLocalScienceDiagramRequest(text) {
    if (!isScienceMode) return false;
    if (/\b(realistic|photorealistic|photo|photograph|lifelike|creative|artistic|cartoon)\b/i.test(text)) {
        return false;
    }
    const hasDiagramIntent = /\b(diagram|draw|drawing|picture|visuali[sz]e|illustrat(?:e|ion)|show\s+me)\b/i.test(text);
    const hasLocalTopic = /\b(free[ -]?body|force|friction|normal force|weight|circuit|battery|resistor|electric current|water cycle|evaporation|condensation|precipitation|plant cell|chloroplast|central vacuole)\b/i.test(text);
    return hasDiagramIntent && hasLocalTopic;
}

function looksLikeImageGenerationRequest(text) {
    if (isGraphRequest(text)) return false;
    if (/\b(?:do not|don't)\s+(?:create|generate|make|draw|produce|design|show)\b/i.test(text)) {
        return false;
    }
    if (isSupportedLocalScienceDiagramRequest(text)) return false;

    const directRequest = /^\s*(?:please\s+)?(?:create|generate|make|draw|sketch|produce|design|show\s+me)\b/i;
    const politeRequest = /\b(?:can|could|would|will)\s+you\s+(?:please\s+)?(?:create|generate|make|draw|sketch|produce|design|show)\b/i;
    const visualSubject = /\b(image|picture|photo|photograph|illustration|visual|diagram|artwork)\b/i;
    return visualSubject.test(text) && (directRequest.test(text) || politeRequest.test(text));
}

function prepareImageGenerationRequest(text) {
    setImageModeActive(true);
    if (imageModeSelect) imageModeSelect.value = requestedImageMode(text);
    userInput.value = text;
    userInput.dispatchEvent(new Event("input"));
    userInput.focus();
}

// ---- Send message ----
async function sendMessage(messageOverride = null, options = {}) {
    if (!await ensureConversationReady()) return;
    const version = chatViewVersion;
    if (messageOverride === null && isImageModeOn()) {
        await generateImage();
        return;
    }
    const hasAttachments = messageOverride === null && Boolean(window.DelphicAttachments?.hasFiles());
    const text = (messageOverride ?? userInput.value).trim()
        || (hasAttachments ? "Please explain the attached material." : "");
    if (!text) return;
    const workCheckIntro = tutorMode === "science" ? "Please check my reasoning:" : "Please check my work:";
    if (!hasAttachments && text === `${workCheckIntro}\nProblem: \nMy steps:`) {
        showWarning("Add your problem and steps before sending, or attach your work.");
        return;
    }
    if (isSending) {
        showWarning("Please wait for the current answer to finish.");
        return;
    }
    if (messageOverride === null && !hasAttachments && looksLikeImageGenerationRequest(text)) {
        if (!imageGenerationEnabled) {
            showWarning("Image generation is disabled in this installation. Enable DELPHIC_ENABLE_EXPERIMENTAL_IMAGES=true and restart the app to use OpenRouter images.");
            return;
        }
        prepareImageGenerationRequest(text);
        await generateImage();
        return;
    }

    const isPlotRequest = !hasAttachments && isGraphRequest(text);
    if (!isPlotRequest && !await ensureAiProviderConfigured()) return;
    if (version !== chatViewVersion || isSending) return;

    isSending = true;
    removeTutorWelcome();
    const userBubble = addMessage("user", text, {
        attachments: hasAttachments ? window.DelphicAttachments.summaries() : [],
    });
    if (messageOverride === null) {
        userInput.value = "";
        userInput.style.height = "auto";
    }
    showSpinner();
    showTyping();

    // Fire plot request in parallel if needed
    let plotPromise = null;
    if (graphingEnabled && isPlotRequest) {
        plotPromise = fetch("/plot", {
            method: "POST",
            headers: getImageRequestHeaders({ "Content-Type": "application/json" }),
            body: JSON.stringify({ message: text }),
        }).catch(err => {
            console.error("[PLOT] fetch error:", err);
            return null;
        });
    }

    const shouldUseLocalGraphOnly = Boolean(
        plotPromise && aiSettingsStatus.loaded && !aiSettingsStatus.configured
    );
    if (shouldUseLocalGraphOnly) {
        hideTyping();
        try {
            const localReply = await saveLocalGraphMessage(text);
            addMessage("assistant", localReply);
            await showPlotResult(plotPromise);
            await loadSessions();
        } catch (error) {
            showWarning(error.message || "I could not save that graph request.");
        } finally {
            hideSpinner();
            isSending = false;
            userInput.focus();
        }
        return;
    }

    let activeStreamBubble = null;
    let drainPendingWords = null;
    try {
        const payload = {
            message: text,
            hint_mode: false,
            check_mode: false,
            step_by_step_mode: isStepByStepModeOn(),
            practice_mode: Boolean(options.practiceMode),
            quiz_mode: Boolean(options.quizMode),
        };
        const requestOptions = hasAttachments
            ? window.DelphicAttachments.buildRequest(payload)
            : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
        const res = await fetch(apiUrl("/stream"), {
            method: "POST",
            headers: getImageRequestHeaders(requestOptions.headers || {}),
            body: requestOptions.body,
        });

        if (!res.ok) {
            hideTyping();
            const errData = await res.json().catch(() => null);
            const errorMessage = errData?.error || "Something went wrong. Please try again.";
            showWarning(errorMessage);
            if (hasAttachments) {
                userBubble.remove();
                if (!userInput.value) userInput.value = text;
                userInput.dispatchEvent(new Event("input"));
            }
            if (/provider|api key/i.test(errorMessage)) {
                openAiSettings(errorMessage, { messageIsError: true });
            }
            hideSpinner();
            userInput.focus();
            return;
        }

        if (hasAttachments) window.DelphicAttachments.clear();

        // Create an empty assistant bubble to stream into
        hideTyping();
        const { bubble, contentDiv, textEl, copyBtn, practiceBtn } = createStreamingBubble();
        activeStreamBubble = bubble;
        let accumulated = "";
        let currentSseEvent = "message";
        let responseFinalized = false;

        // Word-by-word queue — chunks split into words, each word pops in with a short delay
        const wordQueue = [];
        let isPopping = false;
        const WORD_DELAY_MS = 6; // Fast streaming while keeping the response readable.

        function popWord() {
            if (wordQueue.length === 0) {
                isPopping = false;
                return;
            }
            isPopping = true;
            accumulated += wordQueue.shift();
            textEl.innerHTML = wrapMessageTables(sanitizeRenderedHtml(marked.parse(accumulated)));
            bubble.dataset.rawContent = accumulated;
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
        drainPendingWords = waitForQueue;

        async function finalizeStreamedResponse(tokens, finishReason = "unknown", metadata = {}) {
            if (responseFinalized) return;
            if (!Number.isNaN(tokens)) updateTokenCount(tokens);

            responseFinalized = true;
            await waitForQueue();
            await loadSessions(); // refresh sidebar session preview
            // Strip confidence line, then run renderMarkdown (which calls
            // protectLatex) so ALL bracket variants are normalised before KaTeX
            const rawContent = accumulated;
            bubble.dataset.rawContent = rawContent;
            const { cleanText, level } = extractConfidence(rawContent);
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
                trust: false,
            });
            // Show copy and practice controls after completion metadata arrives.
            copyBtn.style.display = "";
            practiceBtn.style.display = "";
            bubble.setAttribute("aria-busy", "false");
            applyResponseMetadata(bubble, { ...metadata, finish_reason: finishReason });
            scrollToBottom();
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = done ? "" : lines.pop();

            for (const rawLine of lines) {
                const line = rawLine.replace(/\r$/, "");
                if (line.startsWith("event: ")) {
                    currentSseEvent = line.slice(7).trim() || "message";
                    continue;
                }
                if (line === "") {
                    currentSseEvent = "message";
                    continue;
                }
                if (!line.startsWith("data: ")) continue;
                const payload = line.slice(6);

                if (currentSseEvent === "complete") {
                    try {
                        const metadata = JSON.parse(payload);
                        const tokens = Number.parseInt(metadata.tokens_used, 10);
                        await finalizeStreamedResponse(
                            tokens,
                            metadata.finish_reason || "unknown",
                            metadata,
                        );
                    } catch (error) {
                        console.warn("[STREAM] Could not read completion metadata:", error);
                    }
                } else if (currentSseEvent === "token") {
                    const chunk = JSON.parse(payload);
                    if (typeof chunk.text !== "string") throw new Error("Invalid streamed text.");
                    enqueueWords(chunk.text);
                } else if (payload.startsWith("[DONE:")) {
                    const tokens = parseInt(payload.slice(6, -1), 10);
                    await finalizeStreamedResponse(tokens);
                } else {
                    // Legacy single-line text is literal; escaped newlines are ambiguous.
                    enqueueWords(payload);
                }
            }
            if (done) break;
        }
        if (!responseFinalized) {
            await finalizeStreamedResponse(Number.NaN);
            const status = document.createElement("span");
            status.className = "response-status";
            status.setAttribute("role", "status");
            status.textContent = "Response ended without a completion status.";
            bubble.querySelector(".response-actions").appendChild(status);
        }
    } catch (err) {
        hideTyping();
        if (activeStreamBubble?.getAttribute("aria-busy") === "true") {
            await drainPendingWords?.();
            activeStreamBubble.setAttribute("aria-busy", "false");
            activeStreamBubble.querySelector(".copy-btn").style.display = "";
            const status = document.createElement("span");
            status.className = "response-status";
            status.setAttribute("role", "status");
            status.textContent = "Response interrupted";
            activeStreamBubble.querySelector(".response-actions").appendChild(status);
        }
        if (hasAttachments && window.DelphicAttachments.hasFiles()) {
            userBubble.remove();
            if (!userInput.value) userInput.value = text;
            userInput.dispatchEvent(new Event("input"));
        }
        addMessage("assistant", "Network error. Please check your connection.");
    } finally {
        hideSpinner();
        userInput.focus();

        // Show graph if we got one
        if (plotPromise) {
            await showPlotResult(plotPromise);
        }
        isSending = false;
    }
}

sendBtn.addEventListener("click", () => sendMessage());
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

// ---- Sidebar topic / quick-action clicks ----
document.querySelectorAll("[data-topic]").forEach((el) => {
    el.addEventListener("click", () => {
        userInput.value = el.getAttribute("data-topic");
        userInput.focus();
        setSidebarOpen(false);
    });
});

document.addEventListener("click", event => {
    if (event.target.closest('[data-composer-action="check-work"]')) {
        if (isSending) return;
        setImageModeActive(false);
        const intro = tutorMode === "science" ? "Please check my reasoning:" : "Please check my work:";
        const draft = userInput.value;
        let cursor;
        if (!draft.trim()) {
            if (window.DelphicAttachments?.hasFiles()) {
                userInput.value = `${intro}\nThe problem and my work are in the attached material.`;
                cursor = userInput.value.length;
            } else {
                userInput.value = `${intro}\nProblem: \nMy steps: `;
                cursor = userInput.value.indexOf("Problem: ") + "Problem: ".length;
            }
        } else if (!/^\s*(?:please\s+)?check my (?:work|reasoning)\b/i.test(draft)) {
            userInput.value = `${intro}\n${draft}`;
        }
        userInput.dispatchEvent(new Event("input"));
        setSidebarOpen(false);
        userInput.focus();
        const position = cursor ?? userInput.value.length;
        userInput.setSelectionRange(position, position);
        return;
    }
    const promptButton = event.target.closest("[data-prompt]");
    if (promptButton) {
        userInput.value = promptButton.getAttribute("data-prompt");
        sendMessage();
        setSidebarOpen(false);
    }
});

loadAiSettingsStatus();
