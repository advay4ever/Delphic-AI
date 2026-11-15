const { test, expect } = require("@playwright/test");

const KEY = "gsk-fake-native-storage-browser-test";
const providers = [
    { id: "groq", label: "Groq", models: [{ id: "groq-a", label: "Groq A" }] },
    { id: "openai", label: "OpenAI", models: [{ id: "openai-a", label: "OpenAI A" }] },
];

async function setup(page, url, options = {}) {
    const state = { posts: [], deleted: 0, failDelete: false, failSave: false, value: {
        configured: true, provider: "groq", model: "groq-a", source: "session", can_forget: true,
        providers, device_storage: true, device_storage_available: true,
        remember_key: false, has_saved_key: false, ...options,
    } };
    await page.route("**/ai-settings", async route => {
        const method = route.request().method();
        if (method === "POST") {
            const body = route.request().postDataJSON();
            state.posts.push(body);
            if (state.failSave) return route.fulfill({ status: 503, json: { error: "Could not save the key in protected storage." } });
            state.value = { ...state.value, provider: body.provider, model: body.model,
                remember_key: body.remember_key, has_saved_key: body.remember_key, configured: true };
        }
        if (method === "DELETE") {
            state.deleted++;
            if (state.failDelete) return route.fulfill({ status: 503, json: { error: "Could not remove the saved key." } });
            state.value = { ...state.value, remember_key: false, has_saved_key: false, configured: false, can_forget: false };
        }
        await route.fulfill({ json: state.value });
    });
    await page.goto(url);
    await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-loaded", "true");
    await page.locator("#aiSettingsBtn").click();
    return state;
}

for (const url of ["/#tutor", "/science"]) {
    for (const width of [1280, 1024]) {
        test(`${url} desktop key remembering is opt-in and fits ${width}`, async ({ page }, testInfo) => {
            await page.setViewportSize({ width, height: 800 });
            const state = await setup(page, url);
            const checkbox = page.getByRole("checkbox", { name: "Remember key on this device" });
            await expect(checkbox).toBeVisible();
            await expect(checkbox).not.toBeChecked();
            await checkbox.check();
            await page.getByRole("button", { name: "Close AI settings", exact: true }).click();
            await page.evaluate(() => loadAiSettingsStatus());
            await page.locator("#aiSettingsBtn").click();
            await expect(checkbox).toBeChecked();
            await page.locator("#aiSettingsSubmitBtn").click();
            await expect(page.locator("#aiSettingsModal")).toBeHidden();
            expect(state.posts[0]).toMatchObject({ provider: "groq", api_key: "", remember_key: true });
            await page.reload();
            await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-loaded", "true");
            await page.locator("#aiSettingsBtn").click();
            await expect(checkbox).toBeChecked();
            await expect(page.getByRole("button", { name: "Forget saved key" })).toBeVisible();
            const box = await page.locator(".ai-settings-panel").boundingBox();
            expect(box.x).toBeGreaterThanOrEqual(0);
            expect(box.x + box.width).toBeLessThanOrEqual(width);
            const saveButton = await page.locator("#aiSettingsSubmitBtn").boundingBox();
            expect(saveButton.y + saveButton.height).toBeLessThanOrEqual(box.y + box.height);
            expect(await page.locator(".ai-settings-panel").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
            await page.screenshot({ path: testInfo.outputPath("remember-key.png"), animations: "disabled" });
            await checkbox.uncheck();
            await page.locator("#aiSettingsSubmitBtn").click();
            await expect(page.locator("#aiSettingsModal")).toBeHidden();
            expect(state.posts.at(-1).remember_key).toBe(false);
        });
    }
}

test("vault failures preserve drafts and forgetting must succeed before claiming removal", async ({ page }) => {
    const state = await setup(page, "/#tutor", { remember_key: true, has_saved_key: true, source: "device" });
    state.failDelete = true;
    await page.getByRole("button", { name: "Forget saved key" }).click();
    await expect(page.locator("#aiSettingsMessage")).toContainText("Could not remove");
    await expect(page.locator("#aiRememberKey")).toBeChecked();
    state.failDelete = false;
    await page.getByRole("button", { name: "Forget saved key" }).click();
    await expect(page.locator("#aiRememberKey")).not.toBeChecked();
    await expect(page.locator("#aiSettingsMessage")).toContainText("were forgotten");
    await page.locator("#aiApiKeyInput").fill(KEY);
    await page.locator("#aiRememberKey").check();
    state.failSave = true;
    await page.locator("#aiSettingsSubmitBtn").click();
    await expect(page.locator("#aiSettingsMessage")).toContainText("Could not save");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue(KEY);
    expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain(KEY);
});

test("web and unsupported desktop storage do not offer a working remember switch", async ({ page }) => {
    await setup(page, "/#tutor", { device_storage: false, device_storage_available: false });
    await expect(page.locator("#aiRememberKeyField")).toBeHidden();
    await page.evaluate(() => {
        applyAiSettingsStatus({ ...aiSettingsStatus, device_storage: true, device_storage_available: false });
        updateAiSettingsFormState();
    });
    await expect(page.locator("#aiRememberKeyField")).toBeVisible();
    await expect(page.locator("#aiRememberKey")).toBeDisabled();
    await expect(page.locator("#aiSettingsHelp")).toContainText("unavailable");
});

test("switching provider does not automatically remember the next provider", async ({ page }) => {
    await setup(page, "/science", { remember_key: true, has_saved_key: true, source: "device" });
    await expect(page.locator("#aiRememberKey")).toBeChecked();
    await page.locator("#aiProviderSelect").selectOption("openai");
    await expect(page.locator("#aiRememberKey")).not.toBeChecked();
    await expect(page.getByRole("button", { name: "Forget saved key" })).toBeVisible();
});
