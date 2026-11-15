const { test, expect } = require("@playwright/test");


const TEST_KEY = "gsk-browser-phase-three-secret-key";
const PROVIDERS = [
    {
        id: "groq",
        label: "Groq",
        model: "openai/gpt-oss-120b",
        models: [
            { id: "openai/gpt-oss-120b", label: "GPT-OSS 120B (recommended)" },
            { id: "openai/gpt-oss-20b", label: "GPT-OSS 20B" },
        ],
    },
    {
        id: "openrouter",
        label: "OpenRouter",
        model: "openai/gpt-5.6-terra",
        models: [
            { id: "openai/gpt-5.6-terra", label: "GPT-5.6 Terra (recommended)" },
        ],
    },
];
const IMAGE_MODELS = [
    { id: "openai/gpt-image-2.5-sunburst", label: "Best quality - GPT Image 2.5 Sunburst" },
    { id: "openai/gpt-image-2.5-flare", label: "Faster - GPT Image 2.5 Flare" },
];


function publicStatus(
    configured,
    model = "openai/gpt-oss-120b",
    provider = "groq",
    imageModel = IMAGE_MODELS[0].id,
) {
    return {
        configured,
        provider,
        model,
        image_model: imageModel,
        image_models: IMAGE_MODELS,
        source: configured ? "session" : null,
        can_forget: configured,
        providers: PROVIDERS,
    };
}


async function mockSharedAiSettings(context, initiallyConfigured = false) {
    const state = {
        configured: initiallyConfigured,
        provider: "groq",
        model: "openai/gpt-oss-120b",
        imageModel: IMAGE_MODELS[0].id,
        requests: [],
    };

    await context.route("**/ai-settings", async route => {
        const request = route.request();
        if (request.method() === "POST") {
            const body = request.postDataJSON();
            state.requests.push(body);
            state.configured = true;
            state.provider = body.provider;
            state.model = body.model;
            state.imageModel = body.image_model;
        } else if (request.method() === "DELETE") {
            state.configured = false;
            state.provider = "groq";
        }

        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(publicStatus(
                state.configured,
                state.model,
                state.provider,
                state.imageModel,
            )),
        });
    });

    return state;
}


test("API setup stays out of the way and is shared safely across tabs", async ({ context }) => {
    const state = await mockSharedAiSettings(context);
    const mathPage = await context.newPage();
    await mathPage.goto("/#tutor");
    await expect(mathPage.locator("#aiSettingsModal")).toBeHidden();
    await expect(mathPage.locator("#aiSettingsBtn")).toHaveText("Connect AI");

    const sciencePage = await context.newPage();
    await sciencePage.goto("/science");
    await expect(sciencePage.locator("#aiSettingsModal")).toBeHidden();

    await mathPage.bringToFront();
    await mathPage.locator("#aiSettingsBtn").click();
    await expect(mathPage.locator("#aiSettingsModal")).toBeVisible();
    await mathPage.locator("#aiApiKeyInput").fill(TEST_KEY);
    await mathPage.getByRole("button", { name: "Show API key" }).click();
    await expect(mathPage.locator("#aiApiKeyInput")).toHaveAttribute("type", "text");
    await mathPage.getByRole("button", { name: "Hide API key" }).click();
    await expect(mathPage.locator("#aiApiKeyInput")).toHaveAttribute("type", "password");
    await mathPage.locator("#aiSettingsForm").getByRole("button", { name: "Connect" }).click();

    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveText("Settings");
    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
    await expect(sciencePage.locator("#aiSettingsModal")).toBeHidden();
    await expect(mathPage.locator("#aiApiKeyInput")).toHaveValue("");

    await sciencePage.reload();
    await expect(sciencePage.locator("#aiSettingsModal")).toBeHidden();
    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveText("Settings");
    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");

    for (const page of [mathPage, sciencePage]) {
        const browserData = await page.evaluate(() => ({
            localStorage: { ...localStorage },
            sessionStorage: { ...sessionStorage },
            keyInput: document.querySelector("#aiApiKeyInput")?.value || "",
            html: document.documentElement.outerHTML,
        }));
        expect(JSON.stringify(browserData)).not.toContain(TEST_KEY);
    }

    await sciencePage.locator("#aiSettingsBtn").click();
    await expect(sciencePage.locator("#aiConnectionStatus")).toContainText("Configured");
    await expect(sciencePage.locator("#aiConnectionStatus")).toContainText("Groq key configured. Connection not verified.");
    await expect(sciencePage.locator("#aiKeyEntry")).toBeHidden();
    await expect(sciencePage.getByRole("button", { name: "Replace API key" })).toBeVisible();
    await expect(sciencePage.getByRole("button", { name: "Forget API key" })).toBeVisible();
    await sciencePage.getByRole("button", { name: "Forget API key" }).click();

    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveText("Connect AI");
    await expect(mathPage.locator("#aiSettingsBtn")).toHaveText("Connect AI");
    await expect(sciencePage.locator("#aiSettingsModal")).toBeVisible();
    await expect(mathPage.locator("#aiSettingsModal")).toBeHidden();
    expect(state.configured).toBe(false);
});


test("an active provider can change models without re-entering its key", async ({ context, page }) => {
    const state = await mockSharedAiSettings(context, true);
    await page.goto("/#tutor");
    await expect(page.locator("#aiSettingsModal")).toBeHidden();

    await page.locator("#aiSettingsBtn").click();
    await page.locator("#aiModelSelect").selectOption("openai/gpt-oss-20b");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    await page.locator("#aiSettingsForm").getByRole("button", { name: "Save changes" }).click();

    expect(state.requests).toHaveLength(1);
    expect(state.requests[0]).toEqual({
        provider: "groq",
        api_key: "",
        model: "openai/gpt-oss-20b",
        image_model: "openai/gpt-image-2.5-sunburst",
    });
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
});

test("AI settings overlays the chat and styles key replacement in both tutors", async ({ context, page }, testInfo) => {
    await mockSharedAiSettings(context, true);
    for (const url of ["/#tutor", "/science"]) {
        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 844 });
            await page.goto(url);
            await expect(page.locator("#aiSettingsBtn")).toHaveText("Settings");
            await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
            await page.locator(".sidebar").evaluate(async element => {
                await Promise.all(element.getAnimations().map(animation => animation.finished.catch(() => {})));
            });
            const before = await page.locator(".chat-main").boundingBox();
            await page.locator("#aiSettingsBtn").click();
            const modal = page.locator("#aiSettingsModal");
            await expect(modal).toHaveCSS("position", "fixed");
            await expect(page.locator("#aiKeyEntry")).toBeHidden();
            await page.getByRole("button", { name: "Replace API key", exact: true }).click();
            await expect(page.locator("#aiApiKeyInput")).toBeVisible();
            await expect(page.locator("#aiApiKeyInput")).toBeFocused();
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(value => document.documentElement.dataset.theme = value, theme);
                const after = await page.locator(".chat-main").boundingBox();
                expect(after.width).toBeCloseTo(before.width, 0);
                const panel = await page.locator(".ai-settings-panel").boundingBox();
                expect(panel.width).toBeCloseTo(Math.min(420, width - 36), 0);
                expect(panel.x).toBeGreaterThanOrEqual(12);
                expect(panel.x + panel.width).toBeLessThanOrEqual(width - 12);
                expect(panel.y).toBeGreaterThanOrEqual(12);
                expect(panel.y + panel.height).toBeLessThanOrEqual(832);
                expect(await page.locator(".ai-settings-panel").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
                const styles = await page.locator(".ai-settings-panel").evaluate(el => ({
                    padding: parseFloat(getComputedStyle(el).paddingTop),
                    background: getComputedStyle(el).backgroundColor,
                }));
                expect(styles.padding).toBeGreaterThanOrEqual(16);
                expect(styles.background).not.toBe("rgba(0, 0, 0, 0)");
                expect((await page.locator("#aiApiKeyInput").boundingBox()).height).toBeGreaterThanOrEqual(44);
                await page.locator("#aiApiKeyInput").fill(TEST_KEY);
                await expect(page.locator(".ai-key-eye")).toBeVisible();
                await expect(page.locator(".ai-key-eye-off")).toBeHidden();
                await page.getByRole("button", { name: "Show API key", exact: true }).click();
                await expect(page.locator(".ai-key-eye-off")).toBeVisible();
                await expect(page.locator(".ai-key-eye")).toBeHidden();
                await page.getByRole("button", { name: "Hide API key", exact: true }).click();
                await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`settings-${url === "/science" ? "science" : "math"}-${width}-${theme}.png`) });
            }
            await page.locator("#aiSettingsSubmitBtn").focus();
            await page.keyboard.press("Tab");
            await expect(page.getByRole("button", { name: "Close AI settings", exact: true })).toBeFocused();
            await page.keyboard.press("Shift+Tab");
            await expect(page.locator("#aiSettingsSubmitBtn")).toBeFocused();
            await page.keyboard.press("Escape");
            await expect(modal).toBeHidden();
            await expect(page.locator("#aiSettingsBtn")).toBeFocused();
        }
    }
});


test("OpenRouter image quality can be selected and stays visible without exposing the key", async ({ context, page }) => {
    const state = await mockSharedAiSettings(context);
    await page.goto("/#tutor");
    await page.locator("#aiSettingsBtn").click();
    await page.locator("#aiProviderSelect").selectOption("openrouter");

    await expect(page.locator("#aiImageModelField")).toBeVisible();
    await expect(page.locator("#aiImageModelSelect option")).toHaveCount(2);
    await page.locator("#aiImageModelSelect").selectOption("openai/gpt-image-2.5-flare");
    await page.getByRole("button", { name: "Close AI settings", exact: true }).click();
    await page.evaluate(() => loadAiSettingsStatus());
    await page.locator("#aiSettingsBtn").click();
    await expect(page.locator("#aiProviderSelect")).toHaveValue("openrouter");
    await expect(page.locator("#aiImageModelSelect")).toHaveValue("openai/gpt-image-2.5-flare");
    await page.locator("#aiApiKeyInput").fill("sk-or-v1-browser-test-key");
    await page.getByRole("button", { name: "Connect", exact: true }).click();

    expect(state.requests).toHaveLength(1);
    expect(state.requests[0]).toEqual({
        provider: "openrouter",
        api_key: "sk-or-v1-browser-test-key",
        model: "openai/gpt-5.6-terra",
        image_model: "openai/gpt-image-2.5-flare",
    });
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
    await expect(page.locator("#aiSettingsModal")).toBeHidden();

    await page.locator("#aiSettingsBtn").click();
    await expect(page.locator("#aiConnectionStatus")).toContainText("OpenRouter key configured. Connection not verified.");
    await expect(page.locator("#aiKeyEntry")).toBeHidden();
    await expect(page.locator("#aiImageModelSelect")).toHaveValue("openai/gpt-image-2.5-flare");
    await page.getByRole("button", { name: "Replace API key" }).click();
    await expect(page.locator("#aiKeyEntry")).toBeVisible();
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");

    const browserData = await page.evaluate(() => ({
        localStorage: { ...localStorage },
        sessionStorage: { ...sessionStorage },
        html: document.documentElement.outerHTML,
    }));
    expect(JSON.stringify(browserData)).not.toContain("sk-or-v1-browser-test-key");
});


test("the real backend shares only a random settings ID with Math and Science", async ({ context, page }) => {
    await page.goto("/#tutor");
    const savedStatus = await page.evaluate(async key => {
        const response = await fetch("/ai-settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider: "groq",
                api_key: key,
                model: "llama-3.1-8b-instant",
            }),
        });
        return { status: response.status, body: await response.json() };
    }, TEST_KEY);

    expect(savedStatus.status).toBe(200);
    expect(savedStatus.body.source).toBe("session");
    expect(JSON.stringify(savedStatus)).not.toContain(TEST_KEY);

    const sciencePage = await context.newPage();
    await sciencePage.goto("/science");
    await expect(sciencePage.locator("#aiSettingsModal")).toBeHidden();
    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveText("Settings");
    await expect(sciencePage.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
    const scienceStatus = await sciencePage.evaluate(async () => {
        const response = await fetch("/ai-settings");
        return response.json();
    });
    expect(scienceStatus).toMatchObject({
        configured: true,
        provider: "groq",
        model: "llama-3.1-8b-instant",
        source: "session",
        can_forget: true,
    });

    const browserData = {
        cookies: await context.cookies(),
        storage: await sciencePage.evaluate(() => ({
            localStorage: { ...localStorage },
            sessionStorage: { ...sessionStorage },
        })),
    };
    expect(JSON.stringify(browserData)).not.toContain(TEST_KEY);

    const forgottenStatus = await sciencePage.evaluate(async () => {
        const response = await fetch("/ai-settings", { method: "DELETE" });
        return response.json();
    });
    expect(forgottenStatus.source).not.toBe("session");
    expect(JSON.stringify(forgottenStatus)).not.toContain(TEST_KEY);
});


test("the settings dialog fits a phone and stays open after an immediate forget", async ({ context, page }) => {
    await mockSharedAiSettings(context);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/#tutor");
    await expect(page.locator("#aiSettingsModal")).toBeHidden();
    await page.locator("#aiSettingsBtn").click();

    for (const theme of ["light", "dark", "neon"]) {
        await page.evaluate(value => {
            document.documentElement.setAttribute("data-theme", value);
        }, theme);
        const box = await page.locator(".ai-settings-panel").boundingBox();
        expect(box).not.toBeNull();
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.y).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(390);
        expect(box.y + box.height).toBeLessThanOrEqual(844);
    }

    await page.locator("#aiApiKeyInput").fill(TEST_KEY);
    await page.locator("#aiSettingsForm").getByRole("button", { name: "Connect" }).click();
    await page.getByRole("button", { name: "Forget API key" }).click();
    await page.waitForTimeout(850);

    await expect(page.locator("#aiSettingsModal")).toBeVisible();
    await expect(page.locator("#aiSettingsBtn")).toHaveText("Connect AI");
    await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
});


test("an AI-only question asks for setup once without losing the student's draft", async ({ context, page }) => {
    await mockSharedAiSettings(context);
    await page.goto("/#tutor");
    await expect(page.locator("#aiSettingsModal")).toBeHidden();

    const input = page.locator("#userInput");
    await input.fill("Explain why dividing by zero is not allowed");
    await page.locator("#sendBtn").click();

    await expect(page.locator("#aiSettingsModal")).toBeVisible();
    await expect(page.locator("#aiSettingsMessage")).toContainText("Connect AI to send this question");
    await expect(input).toHaveValue("Explain why dividing by zero is not allowed");
    await expect(page.locator(".message.user")).toHaveCount(0);
    await page.screenshot({ path: "/tmp/delphic-api-settings.png", fullPage: true });

    await page.getByRole("button", { name: "Not now" }).click();
    await expect(page.locator("#aiSettingsModal")).toBeHidden();
    await expect(input).toHaveValue("Explain why dividing by zero is not allowed");

    await page.reload();
    await expect(page.locator("#aiSettingsModal")).toBeHidden();
});


test("local graphing works without forcing the AI setup dialog", async ({ context, page }) => {
    await mockSharedAiSettings(context);
    await page.goto("/#tutor");

    await page.locator("#userInput").fill("Graph y = x^2");
    await page.locator("#sendBtn").click();

    await expect(page.locator("#aiSettingsModal")).toBeHidden();
    await expect(page.locator(".message.user").last()).toContainText("Graph y = x^2");
    await expect(page.locator(".local-graph-container canvas").last()).toBeVisible();
});


test("localhost page navigation uses the shared 127.0.0.1 address", async ({ page }) => {
    const testPort = process.env.DELPHIC_TEST_PORT || "5001";
    await page.goto(`http://localhost:${testPort}/science?topic=forces`);

    await expect(page).toHaveURL(`http://127.0.0.1:${testPort}/science?topic=forces`);
});
