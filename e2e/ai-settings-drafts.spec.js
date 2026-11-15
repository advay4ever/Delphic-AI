const { test, expect } = require("@playwright/test");

const KEY = "sk-test-draft-only-not-a-real-key";
const providers = [
    { id: "groq", label: "Groq", models: [{ id: "groq-a", label: "Groq A" }] },
    { id: "openai", label: "OpenAI", models: [{ id: "openai-a", label: "OpenAI A" }, { id: "openai-b", label: "OpenAI B" }] },
];
function status(configured = true) {
    return { configured, provider: "groq", model: "groq-a", providers, can_forget: configured, source: configured ? "session" : null };
}
async function setup(page, url = "/#tutor") {
    const state = { value: status(), posts: [] };
    await page.route("**/ai-settings", async route => {
        if (route.request().method() === "POST") {
            state.posts.push(route.request().postDataJSON());
            state.value = { ...state.value, ...state.posts.at(-1), configured: true };
            delete state.value.api_key;
        }
        await route.fulfill({ json: state.value });
    });
    await page.goto(url);
    await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-loaded", "true");
    await page.locator("#aiSettingsBtn").click();
    return state;
}
async function draft(page) {
    await page.locator("#aiProviderSelect").selectOption("openai");
    await page.locator("#aiModelSelect").selectOption("openai-b");
    await page.locator("#aiApiKeyInput").fill(KEY);
}
async function refresh(page) {
    const response = page.waitForResponse(r => r.url().endsWith("/ai-settings") && r.request().method() === "GET");
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await response;
}

for (const url of ["/#tutor", "/science"]) {
    test(`${url} closing to copy a key preserves provider and model without saving`, async ({ page }) => {
        const state = await setup(page, url);
        await page.locator("#aiProviderSelect").selectOption("openai");
        await page.locator("#aiModelSelect").selectOption("openai-b");
        await page.getByRole("button", { name: "Close AI settings", exact: true }).click();
        await refresh(page);
        await page.evaluate(() => handleAiSettingsTabEvent({ sender: "another-tab", type: "saved" }));
        await page.locator("#aiSettingsBtn").click();
        await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
        await expect(page.locator("#aiModelSelect")).toHaveValue("openai-b");
        await expect(page.locator("#aiKeyEntry")).toBeVisible();
        expect(state.value.provider).toBe("groq");
        expect(state.posts).toEqual([]);
        await page.locator("#aiApiKeyInput").fill(KEY);
        await page.locator("#aiSettingsSubmitBtn").click();
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        expect(state.posts).toHaveLength(1);
        expect(state.posts[0]).toMatchObject({ provider: "openai", model: "openai-b", api_key: KEY });
        await page.locator("#aiSettingsBtn").click();
        await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
        await expect(page.locator("#aiModelSelect")).toHaveValue("openai-b");
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    });
}

test("Escape clears an unsaved key but keeps choices only until page reload", async ({ page }) => {
    const state = await setup(page);
    await draft(page);
    await page.getByRole("button", { name: "Show API key", exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    await refresh(page);
    await page.locator("#aiSettingsBtn").click();
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
    await expect(page.locator("#aiModelSelect")).toHaveValue("openai-b");
    await expect(page.locator("#aiApiKeyInput")).toHaveAttribute("type", "password");
    expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(KEY);
    expect(state.posts).toEqual([]);
    await page.reload();
    await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-loaded", "true");
    await page.locator("#aiSettingsBtn").click();
    await expect(page.locator("#aiProviderSelect")).toHaveValue("groq");
});

test("focus refresh cannot send an OpenAI draft key to Groq", async ({ page }) => {
    const state = await setup(page);
    await draft(page);
    await refresh(page);
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
    await expect(page.locator("#aiModelSelect")).toHaveValue("openai-b");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
    await page.locator("#aiSettingsSubmitBtn").click();
    await expect.poll(() => state.posts.length).toBe(1);
    expect(state.posts[0]).toMatchObject({ provider: "openai", model: "openai-b", api_key: KEY });
});

test("cross-tab save and forgetting update status without discarding a draft", async ({ page }) => {
    const state = await setup(page);
    await draft(page);
    await page.evaluate(() => handleAiSettingsTabEvent({ sender: "another-tab", type: "saved" }));
    await expect(page.locator("#aiSettingsModal")).toBeVisible();
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
    state.value = status(false);
    await page.evaluate(() => handleAiSettingsTabEvent({ sender: "another-tab", type: "forgotten" }));
    await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "false");
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
});

test("expiry removes key reuse without losing an unsaved model choice", async ({ page }) => {
    const state = await setup(page);
    // A model change is a draft even when no replacement key was entered.
    await page.locator("#aiModelSelect").dispatchEvent("change");
    state.value = status(false);
    await refresh(page);
    await expect(page.locator("#aiConnectionStatus")).toBeHidden();
    await expect(page.locator("#aiKeyEntry")).toBeVisible();
    await page.locator("#aiSettingsSubmitBtn").click();
    expect(state.posts).toEqual([]);
    await expect(page.locator("#aiSettingsMessage")).toContainText("Paste an API key");
});

test("late status responses preserve edits started after the request", async ({ page }) => {
    await setup(page);
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route("**/ai-settings", async route => {
        await gate;
        await route.fulfill({ json: status() });
    });
    const requested = page.waitForRequest(r => r.url().endsWith("/ai-settings"));
    const refreshing = page.evaluate(() => loadAiSettingsStatus());
    await requested;
    await draft(page);
    release();
    await refreshing;
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
});

test("a delayed save cannot erase a newer draft", async ({ page }) => {
    await setup(page);
    await draft(page);
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route("**/ai-settings", async route => {
        if (route.request().method() !== "POST") return route.fallback();
        await gate;
        await route.fulfill({ json: { ...status(), provider: "openai", model: "openai-b" } });
    });
    const requested = page.waitForRequest(r => r.method() === "POST" && r.url().endsWith("/ai-settings"));
    await page.locator("#aiSettingsSubmitBtn").click();
    await requested;
    await page.locator("#aiApiKeyInput").fill(KEY + "-newer");
    release();
    await expect(page.locator("#aiSettingsSubmitBtn")).toBeEnabled();
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY + "-newer");
    await page.waitForTimeout(750);
    await expect(page.locator("#aiSettingsModal")).toBeVisible();
});

for (const editAfterReopening of [false, true]) {
    test(`closing during a save preserves completion and protects newer edits: ${editAfterReopening}`, async ({ page }) => {
        const state = await setup(page);
        await draft(page);
        let release;
        const gate = new Promise(resolve => { release = resolve; });
        await page.route("**/ai-settings", async route => {
            if (route.request().method() !== "POST") return route.fallback();
            await gate;
            state.value = { ...status(), provider: "openai", model: "openai-b" };
            await route.fulfill({ json: state.value });
        });
        const requested = page.waitForRequest(r => r.method() === "POST" && r.url().endsWith("/ai-settings"));
        await page.locator("#aiSettingsSubmitBtn").click();
        await requested;
        await page.getByRole("button", { name: "Close AI settings", exact: true }).click();
        if (editAfterReopening) {
            await page.locator("#aiSettingsBtn").click();
            await page.locator("#aiModelSelect").selectOption("openai-a");
        }
        release();
        await expect(page.locator("#aiSettingsSubmitBtn")).toBeEnabled();
        if (editAfterReopening) {
            await page.waitForTimeout(750);
            await expect(page.locator("#aiSettingsModal")).toBeVisible();
            await expect(page.locator("#aiModelSelect")).toHaveValue("openai-a");
        } else {
            // A completed save must not leave a hidden dirty draft blocking later status changes.
            await page.evaluate(() => handleAiSettingsTabEvent({ sender: "another-tab", type: "saved" }));
            state.value = status();
            await refresh(page);
            await page.locator("#aiSettingsBtn").click();
            await expect(page.locator("#aiProviderSelect")).toHaveValue("groq");
        }
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    });
}

test("switching provider explicitly clears its draft key and failed saves retain the new draft", async ({ page }) => {
    await setup(page);
    await draft(page);
    await page.locator("#aiProviderSelect").selectOption("groq");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    await draft(page);
    await page.route("**/ai-settings", route => route.fulfill({ status: 400, json: { error: "Fake rejected key" } }));
    await page.locator("#aiSettingsSubmitBtn").click();
    await expect(page.locator("#aiSettingsMessage")).toContainText("Fake rejected key");
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openai");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
    const storage = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
    expect(storage).not.toContain(KEY);
});
