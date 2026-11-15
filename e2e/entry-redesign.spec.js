const { test, expect } = require("@playwright/test");

const png = {
    name: "worksheet.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKqWQAAAABJRU5ErkJggg==", "base64"),
};
const sse = 'data: Let us work through it.\n\nevent: complete\ndata: {"tokens_used":3,"finish_reason":"complete","can_continue":false}\n\ndata: [DONE:3]\n\n';
const urlFor = mode => mode === "science" ? "/science" : "/#tutor";

async function mockWorkspace(page, mode, messages = []) {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "entry-test", messages, images: [], tokens_used: 0,
    } }));
    await page.route("**/sessions", route => route.fulfill({ json: {
        current_session_id: "entry-test", sessions: [],
    } }));
    await page.route("**/sessions/new", route => route.fulfill({ json: { session_id: "entry-new" } }));
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 0 } }));
    await page.route("**/stream", route => route.fulfill({ contentType: "text/event-stream", body: sse }));
}

async function newChat(page) {
    if (!await page.locator("#newChatBtn").isVisible()) await page.locator("#menuBtn").click();
    await page.locator("#newChatBtn").click();
    await expect(page.locator("#chatWorkspace")).toHaveClass(/is-empty/);
}

test("Math has no work-check shortcut but still accepts students' own work", async ({ page }) => {
    await mockWorkspace(page, "math");
    let payload;
    await page.route("**/stream", route => {
        payload = route.request().postDataJSON();
        return route.fulfill({ contentType: "text/event-stream", body: sse });
    });
    await page.goto(urlFor("math"));
    await expect(page.getByRole("button", { name: "Check my work", exact: true })).toHaveCount(0);
    const work = "Please check my work: 2x + 3 = 11, then 2x = 8, then x = 4.";
    await page.locator("#userInput").fill(work);
    await page.locator("#sendBtn").click();
    await expect.poll(() => payload?.message).toBe(work);
    await expect(page.locator(".message.assistant").last()).toContainText("Let us work through it.");
});

for (const mode of ["science"]) {
    const workCheckLabel = "Check reasoning";
    const workCheckIntro = "Please check my reasoning:";

    test(`${mode} work checking prepares an editable draft without sending an example`, async ({ page }, testInfo) => {
        await page.setViewportSize({ width: 1024, height: 800 });
        await mockWorkspace(page, mode);
        const sent = [];
        await page.route("**/stream", route => {
            sent.push(route.request().postDataJSON());
            return route.fulfill({ contentType: "text/event-stream", body: sse });
        });
        await page.goto(urlFor(mode));
        await page.getByRole("button", { name: workCheckLabel, exact: true }).click();
        await expect(page.locator("#userInput")).toHaveValue(`${workCheckIntro}\nProblem: \nMy steps: `);
        await expect(page.locator("#userInput")).toBeFocused();
        expect(await page.locator("#userInput").evaluate(el => el.selectionStart)).toBe(`${workCheckIntro}\nProblem: `.length);
        await expect(page.locator(".message.user")).toHaveCount(0);
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        expect(sent).toEqual([]);
        await page.screenshot({ path: testInfo.outputPath(`${mode}-work-check-draft.png`), animations: "disabled" });
        await page.locator("#sendBtn").click();
        await expect(page.locator(".input-warning")).toContainText("Add your problem and steps");
        expect(sent).toEqual([]);
        await expect(page.locator(".message.user")).toHaveCount(0);
        const work = "Please check my reasoning: F = ma, m = 2 kg and a = 3 m/s^2, so F = 6 N.";
        await page.locator("#userInput").fill(work);
        await page.locator("#sendBtn").click();
        await expect.poll(() => sent.length).toBe(1);
        expect(sent[0].message).toBe(work);
        await expect(page.locator(".message.user")).toContainText(work);
        await expect(page.locator(".message.assistant").last()).toContainText("Let us work through it.");
    });

    test(`${mode} work checking preserves an existing draft and photo until Send`, async ({ page }) => {
        await mockWorkspace(page, mode);
        let sent;
        await page.route("**/stream", route => {
            sent = route.request().postDataBuffer().toString();
            return route.fulfill({ contentType: "text/event-stream", body: sse });
        });
        await page.goto(urlFor(mode));
        const work = "My problem and handwritten steps are in the worksheet. I am unsure about line 2.";
        await page.locator("#userInput").fill(work);
        await page.locator("#attachmentPhotoInput").setInputFiles(png);
        const check = page.getByRole("button", { name: workCheckLabel, exact: true });
        await check.click();
        await check.click();
        await expect(page.locator("#userInput")).toHaveValue(`${workCheckIntro}\n${work}`);
        await expect(page.locator("#attachmentTray img")).toBeVisible();
        await expect(page.locator(".message.user")).toHaveCount(0);
        expect(sent).toBeUndefined();
        await page.locator("#sendBtn").click();
        await expect.poll(() => sent).toBeTruthy();
        expect(sent).toContain("worksheet.png");
        expect(sent).toContain(work);
        expect(sent).not.toContain("I got x = 5");
    });

    test(`${mode} keyboard work checking exits image mode and supports an uploaded file without setup`, async ({ page }) => {
        await mockWorkspace(page, mode);
        await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
        const costlyRequests = [];
        page.on("request", request => {
            if (request.method() === "POST" && /\/(?:stream|ask|images\/generate|plot)$/.test(new URL(request.url()).pathname)) {
                costlyRequests.push(request.url());
            }
        });
        await page.goto(urlFor(mode));
        await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "false");
        await page.locator("#imageModeBtn").click();
        const check = page.getByRole("button", { name: workCheckLabel, exact: true });
        await check.focus();
        await page.keyboard.press("Enter");
        await expect(page.locator("#imageModeBtn")).toHaveAttribute("aria-pressed", "false");
        await expect(page.locator("#userInput")).toBeFocused();
        await page.locator("#userInput").fill("");
        await page.locator("#attachmentFileInput").setInputFiles({
            name: "my-steps.txt", mimeType: "text/plain", buffer: Buffer.from("My own attempted solution."),
        });
        await check.click();
        await expect(page.locator("#userInput")).toHaveValue(`${workCheckIntro}\nThe problem and my work are in the attached material.`);
        await expect(page.locator("#attachmentTray")).toContainText("my-steps.txt");
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        await expect(page.locator(".message.user")).toHaveCount(0);
        expect(costlyRequests).toEqual([]);
    });

}

for (const mode of ["math", "science"]) {
    test(`${mode} initial welcome and New chat share the same starters and heading`, async ({ page }) => {
        await mockWorkspace(page, mode);
        await page.goto(urlFor(mode));
        const welcome = await page.locator(".welcome-message").innerHTML();
        const starters = page.locator("#composerStarters button");
        const labels = await starters.allTextContents();
        await expect(starters).toHaveCount(mode === "science" ? 6 : 3);
        await expect(page.getByRole("button", { name: "Graph a function", exact: true })).toHaveCount(0);
        await page.locator("#userInput").evaluate(el => { el.dataset.identity = "same-input"; });
        await starters.first().click();
        await expect(page.locator(".message.assistant").last()).toContainText("Let us work through it.");
        await expect(page.locator("#composerStarters")).toBeHidden();
        await expect(page.locator(".welcome-message")).toHaveCount(0);
        expect(await page.locator(".chat-input-area").evaluate(el => getComputedStyle(el).position)).toBe("absolute");
        await newChat(page);
        expect(await page.locator(".welcome-message").innerHTML()).toBe(welcome);
        expect(await starters.allTextContents()).toEqual(labels);
        await expect(page.locator("#userInput")).toHaveAttribute("data-identity", "same-input");
        await expect(page.locator("#composerStarters")).toBeVisible();
        if (mode === "science") await expect(page.getByRole("button", { name: "Show a diagram", exact: true })).toBeVisible();
    });

    test(`${mode} entry fits desktop, tablet, phone, and short screens across themes`, async ({ page }, testInfo) => {
        await mockWorkspace(page, mode);
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        for (const viewport of [
            { width: 1440, height: 900 }, { width: 1024, height: 768 },
            { width: 768, height: 1024 }, { width: 390, height: 844 },
            { width: 320, height: 640 }, { width: 740, height: 390 },
        ]) {
            await page.setViewportSize(viewport);
            await page.goto(urlFor(mode));
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(value => document.documentElement.setAttribute("data-theme", value), theme);
                expect(await page.locator(".tutor-welcome").evaluate(el => {
                    const style = getComputedStyle(el);
                    return [style.backgroundColor, style.borderTopWidth, style.boxShadow];
                })).toEqual(["rgba(0, 0, 0, 0)", "0px", "none"]);
                await page.locator("#sendBtn").scrollIntoViewIfNeeded();
                const pill = await page.locator(".text-pill").boundingBox();
                for (const selector of ["#attachmentBtn", "#addPhotoBtn", "#sendBtn"]) {
                    const box = await page.locator(selector).boundingBox();
                    expect(box.height).toBeGreaterThanOrEqual(44);
                    expect(box.x).toBeGreaterThanOrEqual(pill.x);
                    expect(box.x + box.width).toBeLessThanOrEqual(pill.x + pill.width);
                    expect(box.y + box.height).toBeLessThanOrEqual(pill.y + pill.height);
                }
                const starters = page.locator("#composerStarters button");
                const first = await starters.nth(0).boundingBox();
                const second = await starters.nth(1).boundingBox();
                expect(first.y).toBe(second.y);
                expect(first.x + first.width).toBeLessThan(second.x);
                if (mode === "math") {
                    const practice = await starters.nth(2).boundingBox();
                    const center = (first.x + second.x + second.width) / 2;
                    expect(Math.abs(practice.x + practice.width / 2 - center)).toBeLessThan(1);
                    expect(Math.abs(practice.width - first.width)).toBeLessThan(1);
                    expect(practice.y).toBeGreaterThanOrEqual(first.y + first.height);
                }
                expect(await starters.evaluateAll(items => items.every(el => el.scrollWidth <= el.clientWidth))).toBe(true);
                await page.locator(".step-toggle").scrollIntoViewIfNeeded();
                await expect(page.locator(".step-toggle")).toBeInViewport();
                if (mode === "science") await expect(page.locator("#quizModeBtn")).toBeInViewport();
                expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
                expect(await page.locator("#chatWorkspace").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
                await page.locator("#chatWorkspace").evaluate(el => { el.scrollTop = 0; });
                await page.mouse.move(0, 0);
                await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${mode}-${viewport.width}-${viewport.height}-${theme}.png`) });
            }
        }
        expect(errors).toEqual([]);
    });

    test(`${mode} visible photo action reuses upload validation and survives cancellation`, async ({ page }) => {
        await mockWorkspace(page, mode);
        await page.goto(urlFor(mode));
        await page.locator("#userInput").fill("My unsent question");
        await page.locator("#attachmentPhotoInput").evaluate(el => {
            el.addEventListener("change", event => {
                if (event.target.files.length) window.entryTestFile = event.target.files[0];
            }, { capture: true });
        });
        let chooserPromise = page.waitForEvent("filechooser");
        await page.getByRole("button", { name: "Add photo", exact: true }).click();
        const chooser = await chooserPromise;
        expect(await chooser.element().getAttribute("id")).toBe("attachmentPhotoInput");
        await chooser.setFiles(png);
        await expect(page.locator("#attachmentTray img")).toBeVisible();
        await expect(page.locator("#userInput")).toHaveValue("My unsent question");
        chooserPromise = page.waitForEvent("filechooser");
        await page.locator("#addPhotoBtn").click();
        await (await chooserPromise).setFiles([]);
        await expect(page.locator(".attachment-chip")).toHaveCount(1);
        await expect(page.locator("#userInput")).toHaveValue("My unsent question");
        await page.locator("#attachmentPhotoInput").evaluate(el => {
            const transfer = new DataTransfer();
            transfer.items.add(window.entryTestFile);
            el.files = transfer.files;
            el.dispatchEvent(new Event("change"));
        });
        await expect(page.locator(".attachment-chip")).toHaveCount(1);
        await page.locator("#attachmentPhotoInput").setInputFiles({ name: "bad.exe", mimeType: "application/octet-stream", buffer: Buffer.from("invalid") });
        await expect(page.locator(".input-warning")).toContainText("Supported files");
        await page.getByRole("button", { name: "Remove worksheet.png", exact: true }).click();
        await expect(page.locator("#attachmentTray")).toBeHidden();
        let pending;
        await page.route("**/stream", route => { pending = route; });
        await page.locator("#attachmentPhotoInput").setInputFiles(png);
        await page.locator("#sendBtn").click();
        await expect(page.locator("#addPhotoBtn")).toBeDisabled();
        await expect(page.locator("#attachmentBtn")).toBeDisabled();
        await expect(page.locator("#sendBtn .send-spinner")).toBeVisible();
        await expect.poll(() => Boolean(pending)).toBe(true);
        await pending.fulfill({ contentType: "text/event-stream", body: sse });
        await expect(page.locator("#sendBtn")).toBeEnabled();
        await expect(page.locator("#addPhotoBtn")).toBeEnabled();
        await expect(page.locator("#attachmentTray")).toBeHidden();
    });

    test(`${mode} guided state persists and keyboard submission retains its behavior`, async ({ page }) => {
        await mockWorkspace(page, mode);
        let payload;
        await page.route("**/stream", route => {
            payload = route.request().postDataJSON();
            return route.fulfill({ contentType: "text/event-stream", body: sse });
        });
        await page.goto(urlFor(mode));
        await expect(page.locator("#stepByStepToggle")).not.toBeChecked();
        await page.locator("#stepByStepToggle").focus();
        await page.keyboard.press("Space");
        await expect(page.locator("#stepByStepToggle")).toBeChecked();
        await page.reload();
        await expect(page.locator("#stepByStepToggle")).toBeChecked();
        expect(await page.evaluate(key => localStorage.getItem(key), `${mode}-tutor-step-mode`)).toBe("true");
        await page.locator("#userInput").fill("Explain this");
        await page.keyboard.press("Shift+Enter");
        await page.keyboard.type("one step at a time");
        await page.keyboard.press("Enter");
        await expect.poll(() => payload?.step_by_step_mode).toBe(true);
        expect(payload.message).toBe("Explain this\none step at a time");
        await expect(page.locator("#sendBtn")).toBeEnabled();
        await expect(page.locator("#sendBtn use")).toHaveAttribute("href", /#arrow-up$/);
    });

    test(`${mode} notes tooltip is keyboard accessible and reflects actual status`, async ({ page }) => {
        await mockWorkspace(page, mode);
        let count = 0;
        await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: count } }));
        await page.goto(urlFor(mode));
        const badge = page.locator("#libraryComposerStatus");
        const tooltip = page.getByRole("tooltip");
        await expect(badge).toContainText("Add study notes");
        await expect(page.locator("#libraryComposerIcon")).toBeVisible();
        await badge.focus();
        await expect(tooltip).toBeVisible();
        await expect(tooltip).toContainText("add or select saved notes");
        await page.keyboard.press("Escape");
        await expect(tooltip).toBeHidden();
        await expect(badge).toBeFocused();
        await page.locator("#userInput").focus();
        await badge.focus();
        await expect(tooltip).toBeVisible();
        count = 2;
        await page.reload();
        await expect(badge).toContainText(`2 ${mode === "science" ? "Science" : "Math"} notes enabled`);
        await expect(page.locator("#libraryComposerIcon")).toBeHidden();
        await badge.focus();
        await expect(tooltip).toContainText("choose saved notes");
        count = null;
        await page.reload();
        await expect(badge).toContainText("Notes unavailable");
        await badge.focus();
        await expect(tooltip).toContainText("retry loading");
    });

    test(`${mode} multiline draft and photo survive settings, resize, and rejected send`, async ({ page }) => {
        await mockWorkspace(page, mode);
        await page.route("**/stream", route => route.fulfill({ status: 400, json: { error: "Try a clearer photo." } }));
        await page.goto(urlFor(mode));
        const draft = Array(25).fill("Explain the steps in this worksheet carefully.").join("\n");
        await page.locator("#userInput").fill(draft);
        await page.locator("#attachmentPhotoInput").setInputFiles(png);
        await page.locator("#aiSettingsBtn").click();
        await page.keyboard.press("Escape");
        await page.setViewportSize({ width: 390, height: 844 });
        await expect(page.locator("#userInput")).toHaveValue(draft);
        await expect(page.locator("#attachmentTray img")).toBeVisible();
        await page.locator("#sendBtn").click();
        await expect(page.locator(".input-warning")).toContainText("Try a clearer photo");
        await expect(page.locator("#userInput")).toHaveValue(draft);
        await expect(page.locator("#attachmentTray img")).toBeVisible();
        await expect(page.locator("#sendBtn")).toBeEnabled();
        const pill = await page.locator(".text-pill").boundingBox();
        const input = await page.locator("#userInput").boundingBox();
        const send = await page.locator("#sendBtn").boundingBox();
        expect(input.y + input.height).toBeLessThanOrEqual(send.y);
        expect(send.y + send.height).toBeLessThanOrEqual(pill.y + pill.height);
        expect(await page.locator("#userInput").evaluate(el => el.scrollHeight > el.clientHeight)).toBe(true);
    });

    test(`${mode} growing composer keeps the latest answer clear without pulling older reading down`, async ({ page }) => {
        const messages = Array.from({ length: 16 }, (_, index) => ({
            role: index % 2 ? "assistant" : "user", content: `Message ${index}: ` + "A longer explanation. ".repeat(20),
        }));
        await mockWorkspace(page, mode, messages);
        await page.goto(urlFor(mode));
        await expect(page.locator("#chatWorkspace")).not.toHaveClass(/is-empty/);
        await page.locator("#chatMessages").evaluate(el => {
            el.style.scrollBehavior = "auto";
            el.scrollTop = el.scrollHeight;
        });
        await page.locator("#userInput").fill(Array(20).fill("A multiline question").join("\n"));
        await expect.poll(() => page.evaluate(() => {
            const last = document.querySelector("#chatMessages .message:last-child").getBoundingClientRect();
            return last.bottom <= document.querySelector(".chat-input-area").getBoundingClientRect().top;
        })).toBe(true);
        await page.locator("#chatMessages").evaluate(el => { el.scrollTop = 100; });
        await page.locator("#attachmentPhotoInput").setInputFiles(png);
        await expect.poll(() => page.locator("#chatMessages").evaluate(el => el.scrollTop)).toBe(100);
    });
}

test("Science quiz remains accessible and sends the existing quiz request", async ({ page }) => {
    await mockWorkspace(page, "science");
    let payload;
    await page.route("**/stream", route => {
        payload = route.request().postDataJSON();
        return route.fulfill({ contentType: "text/event-stream", body: sse });
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/science");
    await page.getByRole("button", { name: "Quiz Mode", exact: true }).click();
    await expect.poll(() => payload?.quiz_mode).toBe(true);
    expect(payload.message).toContain("5-question science quiz");
    await expect(page.locator("#quizModeBtn")).toBeEnabled();
    await expect(page.locator("#quizModeBtn")).toHaveText("Quiz Mode");
});
