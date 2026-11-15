const { test, expect } = require("@playwright/test");

async function mockWorkspace(page, mode, configured = true) {
    const base = mode === "science" ? "/science" : "";
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured, provider: "groq", model: "test", can_forget: configured,
        providers: [{ id: "groq", label: "Groq", models: [{ id: "test", label: "Test model" }] }],
    } }));
    await page.route(`**${base}/history`, route => route.fulfill({ json: {
        session_id: "current", messages: [], images: [], tokens_used: 42,
    } }));
    await page.route(`**${base}/sessions`, route => route.fulfill({ json: {
        current_session_id: "current", sessions: [],
    } }));
}

for (const mode of ["math", "science"]) {
    test(`${mode} header and combined Settings fit desktop and touch screens`, async ({ page }, testInfo) => {
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await mockWorkspace(page, mode);
        for (const width of [1440, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 900 });
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            const settings = page.locator("#aiSettingsBtn");
            await expect(settings).toHaveText("Settings");
            await expect(settings).toHaveAttribute("data-configured", "true");
            await expect(page.locator(".chat-header h1")).toHaveText(mode === "math" ? "Math tutor" : "Science tutor");
            await expect(page.locator(".chat-header .theme-picker, .chat-header .header-switch, .sidebar #tokenCount")).toHaveCount(0);
            await expect(page.locator("#themeToggle")).toHaveCount(1);
            await expect(page.locator("#tokenCount")).toHaveCount(1);
            await expect(page.locator("#tokenCount")).toBeHidden();
            const headingBox = await page.locator(".chat-header-title").boundingBox();
            const settingsBox = await settings.boundingBox();
            expect(headingBox.x + headingBox.width).toBeLessThanOrEqual(settingsBox.x);
            expect(settingsBox.x + settingsBox.width).toBeLessThanOrEqual(width);
            expect(settingsBox.height).toBeGreaterThanOrEqual(44);
            await settings.click();
            await expect(page.getByRole("dialog", { name: "Settings", exact: true })).toBeVisible();
            await expect(page.locator("#workspaceSettingsControls #tokenCount")).toHaveText("42");
            await expect(page.locator("#aiConnectionStatus")).toContainText("Groq key configured. Connection not verified.");
            await expect(page.locator(".chat-main")).toHaveAttribute("inert", "");
            for (const theme of ["light", "dark", "neon"]) {
                await page.locator("#themeToggle").click();
                await page.locator(`[data-theme-choice="${theme}"]`).click();
                await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
                await expect(page.locator("#aiSettingsModal")).toBeVisible();
                await expect(page.locator("#themeToggle")).toBeFocused();
                expect(await page.locator(".ai-settings-panel").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
                await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${mode}-${width}-${theme}-settings.png`) });
            }
            await page.keyboard.press("Escape");
            await expect(page.locator("#aiSettingsModal")).toBeHidden();
            await expect(settings).toBeFocused();
            await expect(page.locator(".chat-main")).not.toHaveAttribute("inert", "");
            await page.reload();
            await expect(page.locator("html")).toHaveAttribute("data-theme", "neon");
        }
        expect(errors).toEqual([]);
    });

    test(`${mode} theme menu handles keyboard and Escape before closing Settings`, async ({ page }) => {
        await mockWorkspace(page, mode, false);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await expect(page.locator("#aiSettingsBtn")).toHaveText("Connect AI");
        await page.locator("#aiSettingsBtn").click();
        await page.locator("#aiApiKeyInput").fill("not-a-real-key-unsaved-draft");
        await page.locator("#themeToggle").focus();
        await page.keyboard.press("ArrowDown");
        await expect(page.locator("#themeMenu")).toBeVisible();
        await page.keyboard.press("Home");
        await expect(page.locator('[data-theme-choice="light"]')).toBeFocused();
        await page.keyboard.press("End");
        await expect(page.locator('[data-theme-choice="neon"]')).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(page.locator("#themeMenu")).toBeHidden();
        await expect(page.locator("#aiSettingsModal")).toBeVisible();
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("not-a-real-key-unsaved-draft");
        await expect(page.locator("#themeToggle")).toBeFocused();
        await page.keyboard.press("ArrowDown");
        await page.keyboard.press("Home");
        await page.keyboard.press("Enter");
        await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
        await page.keyboard.press("Escape");
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("");
        await page.locator("#aiSettingsBtn").click();
        await expect(page.locator("#themeMenu")).toBeHidden();
    });

    test(`${mode} usage updates while Settings is hidden`, async ({ page }) => {
        await mockWorkspace(page, mode);
        const base = mode === "science" ? "/science" : "";
        await page.route(`**${base}/stream`, route => route.fulfill({
            contentType: "text/event-stream",
            body: 'data: Here is an explanation.\n\nevent: complete\ndata: {"tokens_used":99,"finish_reason":"complete"}\n\n',
        }));
        await page.goto(base || "/#tutor");
        await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
        await page.locator("#userInput").fill(mode === "math" ? "Explain fractions" : "Explain refraction");
        await page.locator("#sendBtn").click();
        await expect(page.locator("#tokenCount")).toHaveText("99");
        await expect(page.locator("#tokenCount")).toBeHidden();
        await page.locator("#aiSettingsBtn").click();
        await expect(page.locator("#tokenCount")).toBeVisible();
        await expect(page.locator("#tokenCount")).toHaveText("99");
    });

    test(`${mode} mobile header retains access to every workspace destination`, async ({ page }) => {
        await page.setViewportSize({ width: 390, height: 844 });
        await mockWorkspace(page, mode);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.getByRole("button", { name: "Open sidebar", exact: true }).click();
        await expect(page.locator("#menuBtn")).toHaveAttribute("aria-expanded", "true");
        await expect(page.locator(".sidebar-workspace .workspace-switch")).toHaveText(["Home", "Math tutor", "Science tutor"]);
        const otherTutor = page.locator(mode === "math" ? ".sidebar .tutor-link-science" : ".sidebar .tutor-link-math");
        await otherTutor.click();
        await expect(page).toHaveURL(mode === "math" ? /\/science$/ : /\/#tutor$/);
        await page.getByRole("button", { name: "Open sidebar", exact: true }).click();
        await page.keyboard.press("Escape");
        await expect(page.locator("#menuBtn")).toHaveAttribute("aria-expanded", "false");
        await expect(page.locator("#menuBtn")).toBeFocused();
    });
}
