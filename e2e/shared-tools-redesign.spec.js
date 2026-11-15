const { test, expect } = require("@playwright/test");
const { showAddForm, showLibraryList } = require("./helpers/study-library");

const noteText = "Keep equations balanced by doing the same operation to both sides. Check the result by substituting it into the original equation.";
const chatTitle = "Comparing ways to solve a quadratic equation ".repeat(5);

async function mockTools(page, mode) {
    const base = mode === "science" ? "/science" : "";
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", can_forget: true,
        providers: [{ id: "groq", label: "Groq", models: [{ id: "test", label: "Test model" }] }],
    } }));
    await page.route(`**${base}/history`, route => route.fulfill({ json: {
        session_id: "current", messages: [], images: [], tokens_used: 12,
    } }));
    await page.route(`**${base}/sessions`, route => route.fulfill({ json: {
        current_session_id: "current", sessions: [
            { session_id: "current", preview: "A new topic", message_count: 2, title_generated: true },
            { session_id: "past", preview: chatTitle, message_count: 2, title_generated: true },
        ],
    } }));
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 1 } }));
    await page.route("**/library/notes", route => route.fulfill({ json: { notes: [
        { id: "note-one", title: "Balancing equations", subject: "both", text: noteText, enabled: true, revision: 1 },
    ] } }));
}

async function fits(locator, viewport) {
    await expect(locator).toBeVisible();
    const rect = await locator.boundingBox();
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.y).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(viewport.width + 1);
    expect(rect.y + rect.height).toBeLessThanOrEqual(viewport.height + 1);
    expect(await locator.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
}

async function readable(locator) {
    const contrast = await locator.evaluate(el => {
        const style = getComputedStyle(el);
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d");
        const luminance = value => {
            context.fillStyle = value;
            context.fillRect(0, 0, 1, 1);
            const rgb = [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).map(n => {
                n /= 255;
                return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4;
            });
            return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
        };
        const a = luminance(style.color);
        // Resolve tokens including color-mix through the browser's color parser.
        const probe = document.createElement("span");
        probe.style.color = style.getPropertyValue("--tool-surface");
        el.append(probe);
        const surface = luminance(getComputedStyle(probe).color);
        probe.remove();
        return (Math.max(a, surface) + .05) / (Math.min(a, surface) + .05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
}

for (const mode of ["math", "science"]) {
    test(`${mode} shared surfaces, readable labels, and sticky closes fit all themes`, async ({ page }, testInfo) => {
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await mockTools(page, mode);
        for (const viewport of [
            { width: 1440, height: 900 }, { width: 768, height: 1024 },
            { width: 320, height: 480 }, { width: 640, height: 360 },
        ]) {
            await page.setViewportSize(viewport);
            if (page.url() !== "about:blank") {
                // Each layout starts fresh; deliberately leave the previous test draft.
                page.once("dialog", async dialog => {
                    expect(dialog.type()).toBe("beforeunload");
                    await dialog.accept();
                });
            }
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            await expect(page.locator("#aiSettingsBtn")).toHaveText("Settings");
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
                await page.locator("#aiSettingsBtn").click();
                await fits(page.locator(".ai-settings-panel"), viewport);
                await readable(page.locator("#aiSettingsHelp"));
                const surface = await page.locator(".ai-settings-panel").evaluate(el => getComputedStyle(el).backgroundColor);
                await page.locator("#aiSettingsSubmitBtn").scrollIntoViewIfNeeded();
                await fits(page.locator(".ai-settings-close"), viewport);
                await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-${theme}-settings.png`) });
                await page.locator(".ai-settings-close").click();
                await page.locator("#libraryComposerStatus").click();
                await expect(page.locator("#studyLibraryList strong")).toHaveText("Balancing equations");
                await fits(page.locator("#studyLibraryDialog"), viewport);
                await expect(page.locator("#studyLibraryDialog")).toHaveCSS("background-color", surface);
                await readable(page.locator(".library-privacy"));
                await showAddForm(page);
                await page.locator("#studyLibraryText").fill(noteText);
                await page.getByRole("button", { name: "Save note", exact: true }).scrollIntoViewIfNeeded();
                await fits(page.locator("#closeStudyLibrary"), viewport);
                await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-${theme}-library.png`) });
                await page.locator("#closeStudyLibrary").click();
                await expect(page.locator("#libraryComposerStatus")).toBeFocused();
                if (viewport.width <= 768) await page.locator("#menuBtn").click();
                await page.locator(".session-list-item .session-actions-trigger").click();
                await page.getByRole("menuitem", { name: "Delete chat", exact: true }).click();
                await fits(page.locator(".delete-chat-panel"), viewport);
                await expect(page.locator(".delete-chat-panel")).toHaveCSS("background-color", surface);
                await page.getByRole("button", { name: "Keep chat", exact: true }).scrollIntoViewIfNeeded();
                await fits(page.getByRole("button", { name: "Keep chat", exact: true }), viewport);
                await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-${theme}-delete.png`) });
                await page.keyboard.press("Escape");
                if (viewport.width <= 768) await page.keyboard.press("Escape");
            }
        }
        expect(errors).toEqual([]);
    });

    test(`${mode} short-screen menus stay inside the viewport and keep keyboard focus`, async ({ page }, testInfo) => {
        const viewport = { width: 640, height: 300 };
        await page.setViewportSize(viewport);
        await mockTools(page, mode);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.locator("#attachmentBtn").focus();
        await page.keyboard.press("Enter");
        await fits(page.locator("#attachmentMenu"), viewport);
        await page.keyboard.press("End");
        await expect(page.getByRole("menuitem", { name: "Save study notes" })).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(page.locator("#attachmentBtn")).toBeFocused();

        await page.locator("#libraryComposerStatus").click();
        const trigger = page.locator(".library-actions-trigger");
        await expect(trigger).toBeEnabled();
        await trigger.focus();
        await page.keyboard.press("ArrowUp");
        await fits(page.locator(".library-action-menu"), viewport);
        await expect(page.getByRole("menuitem", { name: "Delete", exact: true })).toBeFocused();
        await page.getByRole("menuitem", { name: "Delete", exact: true }).click({ trial: true });
        await page.locator("#closeStudyLibrary").click({ trial: true });
        await page.screenshot({ path: testInfo.outputPath(`${mode}-note-menu.png`) });
        await page.keyboard.press("Home");
        await expect(page.getByRole("menuitem", { name: "Preview", exact: true })).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(trigger).toBeFocused();
        await expect(page.locator("#studyLibraryDialog")).toBeVisible();
        await page.keyboard.press("Escape");

        await page.locator("#aiSettingsBtn").click();
        await page.locator("#themeToggle").focus();
        await page.keyboard.press("ArrowDown");
        await fits(page.locator("#themeMenu"), viewport);
        await page.keyboard.press("End");
        await expect(page.locator('[data-theme-choice="neon"]')).toBeFocused();
        await page.locator('[data-theme-choice="neon"]').click({ trial: true });
        await page.keyboard.press("Escape");
        await expect(page.locator("#aiSettingsModal")).toBeVisible();
        await page.keyboard.press("Escape");
        await page.locator("#menuBtn").click();
        const action = page.locator(".session-list-item .session-actions-trigger");
        await action.click();
        await fits(page.locator(".session-action-menu"), viewport);
        await page.keyboard.press("End");
        await expect(page.getByRole("menuitem", { name: "Delete chat", exact: true })).toBeFocused();
        await page.getByRole("menuitem", { name: "Delete chat", exact: true }).click({ trial: true });
        await page.keyboard.press("Escape");
        await expect(action).toBeFocused();
    });

    test(`${mode} an AI error waits for Study Library without losing either draft`, async ({ page }) => {
        await mockTools(page, mode);
        let release;
        const gate = new Promise(resolve => { release = resolve; });
        await page.route(mode === "science" ? "**/science/stream" : "**/stream", async route => {
            await gate;
            await route.fulfill({ status: 400, json: { error: "API key needs to be replaced." } });
        });
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
        await page.locator("#userInput").fill(mode === "science" ? "Explain gravity" : "Explain fractions");
        await page.locator("#sendBtn").click();
        await page.locator("#libraryComposerStatus").click();
        await showAddForm(page);
        await page.locator("#studyLibraryNoteTitle").fill("New note draft");
        await page.locator("#studyLibraryText").fill(noteText);
        await showLibraryList(page);
        await page.locator(".library-actions-trigger").click();
        await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
        await page.locator("#libraryEditTitle").fill("Unsaved edit draft");
        release();
        await expect(page.locator("#sendBtn")).toBeEnabled();
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        await expect(page.locator("#libraryEditTitle")).toBeFocused();
        await page.locator("#closeStudyLibrary").click();
        await expect(page.locator("#aiSettingsModal")).toBeVisible();
        await expect(page.locator("#aiSettingsMessage")).toHaveText("API key needs to be replaced.");
        await expect(page.locator(".chat-main")).toHaveAttribute("inert", "");
        await page.evaluate(() => window.dispatchEvent(new CustomEvent("study-library-add")));
        await expect(page.locator("#studyLibraryDialog")).toBeHidden();
        await page.keyboard.press("Escape");
        await expect(page.locator("#libraryComposerStatus")).toBeFocused();
        await page.locator("#libraryComposerStatus").click();
        await expect(page.locator("#libraryEditTitle")).toHaveValue("Unsaved edit draft");
        await page.getByRole("button", { name: "Back to Study Library", exact: true }).click();
        await page.getByRole("button", { name: "Keep editing", exact: true }).click();
        await expect(page.locator("#libraryEditTitle")).toHaveValue("Unsaved edit draft");
        await page.getByRole("button", { name: "Back to Study Library", exact: true }).click();
        await page.getByRole("button", { name: "Discard changes", exact: true }).click();
        await showAddForm(page);
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("New note draft");
        await expect(page.locator("#studyLibraryText")).toHaveValue(noteText);
    });

    test(`${mode} delete confirmation isolates focus, restores it, and allows retry`, async ({ page }) => {
        await mockTools(page, mode);
        await page.route(mode === "science" ? "**/science/sessions/delete" : "**/sessions/delete", route =>
            route.fulfill({ status: 500, json: { error: "Could not delete. Please retry." } }));
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        const trigger = page.locator(".session-list-item .session-actions-trigger");
        await trigger.click();
        await page.getByRole("menuitem", { name: "Delete chat", exact: true }).click();
        await expect(page.getByRole("button", { name: "Keep chat", exact: true })).toBeFocused();
        await expect(page.locator("#sidebar")).toHaveAttribute("inert", "");
        await expect(page.locator(".chat-main")).toHaveAttribute("inert", "");
        await page.evaluate(() => document.getElementById("userInput").focus());
        expect(await page.locator("#deleteChatModal").evaluate(el => el.contains(document.activeElement))).toBe(true);
        await page.keyboard.press("Shift+Tab");
        await expect(page.getByRole("button", { name: "Delete chat", exact: true })).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(page.getByRole("button", { name: "Keep chat", exact: true })).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(trigger).toBeFocused();
        await expect(page.locator("#sidebar")).not.toHaveAttribute("inert", "");
        await trigger.click();
        await page.getByRole("menuitem", { name: "Delete chat", exact: true }).click();
        await page.getByRole("button", { name: "Delete chat", exact: true }).click();
        await expect(page.locator(".input-warning")).toContainText("Could not delete. Please retry.");
        await expect(trigger).toBeFocused();
        await trigger.click();
        await expect(page.getByRole("menuitem", { name: "Delete chat", exact: true })).toBeEnabled();
    });

    test(`${mode} deferred Settings waits for deletion and preserves an existing key draft`, async ({ page }) => {
        await mockTools(page, mode);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.locator(".session-list-item .session-actions-trigger").click();
        await page.getByRole("menuitem", { name: "Delete chat", exact: true }).click();
        await page.evaluate(() => openAiSettings("Provider needs attention.", { messageIsError: true }));
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        await expect(page.getByRole("button", { name: "Keep chat", exact: true })).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(page.locator("#aiSettingsModal")).toBeVisible();
        await expect(page.locator("#deleteChatModal")).toBeHidden();
        await page.locator("#replaceAiKeyBtn").click();
        await page.locator("#aiApiKeyInput").fill("not-a-real-key-unsaved");
        await page.evaluate(() => openAiSettings("Another provider error.", { messageIsError: true }));
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("not-a-real-key-unsaved");
        await expect(page.locator("#aiApiKeyInput")).toBeFocused();
        await expect(page.locator("#aiSettingsMessage")).toHaveText("Another provider error.");
        await readable(page.locator("#aiSettingsMessage"));
        await page.keyboard.press("Escape");
        await expect(page.locator(".session-list-item .session-actions-trigger")).toBeFocused();
    });
}

test("competition choices remain reachable on short touch and zoom-equivalent layouts", async ({ page }) => {
    await mockTools(page, "math");
    for (const viewport of [{ width: 640, height: 300 }, { width: 320, height: 480 }]) {
        await page.setViewportSize(viewport);
        await page.goto("/#tutor");
        await page.locator("#menuBtn").click();
        await page.locator("#competitionPracticeBtn").focus();
        await page.keyboard.press("ArrowDown");
        await fits(page.locator("#competitionMenu"), viewport);
        await page.keyboard.press("End");
        await expect(page.locator(".competition-option").last()).toBeFocused();
        await page.locator(".competition-option").last().click({ trial: true });
        await page.keyboard.press("Escape");
        await expect(page.locator("#competitionPracticeBtn")).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(page.locator("#menuBtn")).toHaveAttribute("aria-expanded", "false");
    }
});

test("Study Library fallback menus stay clickable without native popovers", async ({ page }) => {
    await page.addInitScript(() => { HTMLElement.prototype.showPopover = undefined; });
    await page.setViewportSize({ width: 320, height: 360 });
    for (const mode of ["math", "science"]) {
        await mockTools(page, mode);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.locator("#libraryComposerStatus").click();
        const trigger = page.locator(".library-actions-trigger");
        await expect(trigger).toBeEnabled();
        await trigger.focus();
        await page.keyboard.press("ArrowUp");
        await expect(page.locator(".library-action-menu")).not.toHaveAttribute("popover", "manual");
        await fits(page.locator(".library-action-menu"), { width: 320, height: 360 });
        await expect(page.getByRole("menuitem", { name: "Delete", exact: true })).toBeFocused();
        await page.getByRole("menuitem", { name: "Delete", exact: true }).click({ trial: true });
        await page.locator("#closeStudyLibrary").click({ trial: true });
        await page.keyboard.press("Escape");
        await expect(trigger).toBeFocused();
        await expect(page.locator("#studyLibraryDialog")).toBeVisible();
        await page.keyboard.press("Escape");
    }
});
