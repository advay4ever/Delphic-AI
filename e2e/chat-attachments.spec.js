const { test, expect } = require("@playwright/test");

const textFile = (name = "lesson.txt") => ({
    name, mimeType: "text/plain", buffer: Buffer.from("A triangle has three sides."),
});
const png = {
    name: "diagram.png", mimeType: "image/png",
    buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKqWQAAAABJRU5ErkJggg==", "base64"),
};
const sse = 'data: Explained.\n\nevent: complete\ndata: {"tokens_used":1,"finish_reason":"complete","can_continue":false}\n\n';

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "openai", provider_label: "OpenAI", model: "gpt-4.1", providers: [],
    } }));
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "test-chat", messages: [], images: [], tokens_used: 0,
    } }));
});

test("plus menu fits inside the pill and supports keyboard navigation", async ({ page }) => {
    await page.goto("/#tutor");
    const button = page.getByRole("button", { name: "Add photos, files or study notes", exact: true });
    expect(await button.evaluate(element => Boolean(element.closest(".text-pill")))).toBe(true);
    await button.click();
    await expect(page.getByRole("menuitem", { name: "Add photos" })).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitem", { name: "Upload files" })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.locator("#attachmentMenu")).toBeHidden();
    await expect(button).toBeFocused();
});

test("photos preview and filenames render safely with remove controls", async ({ page }) => {
    await page.goto("/#tutor");
    await page.locator("#attachmentPhotoInput").setInputFiles(png);
    await expect(page.locator("#attachmentTray img")).toBeVisible();
    await page.locator("#attachmentFileInput").setInputFiles(textFile("<script>alert(1)</script>.txt"));
    await expect(page.locator("#attachmentTray")).toContainText("<script>alert(1)</script>.txt");
    await expect(page.locator("#attachmentTray script")).toHaveCount(0);
    await page.getByRole("button", { name: "Remove diagram.png", exact: true }).click();
    await expect(page.locator("#attachmentTray img")).toHaveCount(0);
});

for (const url of ["/#tutor", "/science"]) {
    test(`attachments are sent as multipart in ${url} and never routed to image generation`, async ({ page }) => {
        let sent;
        let imageRequests = 0;
        await page.route("**/images/generate", route => { imageRequests++; return route.abort(); });
        await page.route("**/stream", route => {
            sent = route.request();
            return route.fulfill({ contentType: "text/event-stream", body: sse });
        });
        await page.goto(url);
        await page.locator("#attachmentFileInput").setInputFiles(textFile());
        await page.locator("#userInput").fill("Show me a picture of the problem described here");
        await page.locator("#sendBtn").click();
        await expect(page.locator(".message.assistant").last()).toContainText("Explained.");
        expect(sent.headers()["content-type"]).toContain("multipart/form-data; boundary=");
        expect(sent.postDataBuffer().toString()).toContain("lesson.txt");
        expect(imageRequests).toBe(0);
        await expect(page.locator("#attachmentTray")).toBeHidden();
        await expect(page.locator(".message.user .message-attachments")).toContainText("lesson.txt");
    });
}

test("rejected upload preserves the files and question for retry", async ({ page }) => {
    await page.route("**/stream", route => route.fulfill({ status: 400, json: { error: "The photo needs a vision-capable model." } }));
    await page.goto("/#tutor");
    await page.locator("#attachmentPhotoInput").setInputFiles(png);
    await page.locator("#userInput").fill("Explain this picture");
    await page.locator("#sendBtn").click();
    await expect(page.locator("#userInput")).toHaveValue("Explain this picture");
    await expect(page.locator("#attachmentTray img")).toBeVisible();
    await expect(page.locator(".message.user")).toHaveCount(0);
});

test("selecting an attachment leaves generation mode for file analysis", async ({ page }) => {
    await page.goto("/#tutor");
    await page.locator("#imageModeBtn").click();
    await expect(page.locator("#imageModeBtn")).toHaveAttribute("aria-pressed", "true");
    await page.locator("#attachmentPhotoInput").setInputFiles(png);
    await expect(page.locator("#imageModeBtn")).toHaveAttribute("aria-pressed", "false");
});

test("three-file limit and successful new chat cleanup", async ({ page }) => {
    await page.route("**/sessions/new", route => route.fulfill({ json: { session_id: "new-test-chat" } }));
    await page.goto("/#tutor");
    await page.locator("#attachmentFileInput").setInputFiles([textFile("one.txt"), textFile("two.txt"), textFile("three.txt"), textFile("four.txt")]);
    await expect(page.locator(".attachment-chip")).toHaveCount(3);
    await expect(page.locator(".input-warning")).toContainText("at most 3");
    await page.locator("#newChatBtn").click();
    await expect(page.locator("#attachmentTray")).toBeHidden();
});

test("saved attachment names return without exposing file bytes", async ({ page }) => {
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "test-chat", tokens_used: 0, images: [], messages: [{
            id: 1, role: "user", content: "Explain this", attachments: [{ name: "lesson.pdf", kind: "document" }],
        }],
    } }));
    await page.goto("/#tutor");
    await expect(page.locator(".message-attachments")).toHaveText("lesson.pdf");
});

test("composer attachments fit phone and desktop across all themes", async ({ page }, testInfo) => {
    for (const width of [390, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        for (const theme of ["light", "dark", "neon"]) {
            await page.goto("/#tutor");
            await page.evaluate(() => window.DelphicAttachments.clear());
            await page.evaluate(value => document.documentElement.setAttribute("data-theme", value), theme);
            await page.locator("#attachmentPhotoInput").setInputFiles(png);
            await page.locator("#attachmentFileInput").setInputFiles(textFile("very-long-filename-for-a-science-worksheet-and-other-notes.txt"));
            const tray = await page.locator("#attachmentTray").boundingBox();
            const pill = await page.locator(".text-pill").boundingBox();
            expect(tray.y + tray.height).toBeLessThanOrEqual(pill.y);
            expect(tray.x).toBeGreaterThanOrEqual(0);
            expect(tray.x + tray.width).toBeLessThanOrEqual(width);
            await page.locator("#attachmentBtn").click();
            const menu = await page.locator("#attachmentMenu").boundingBox();
            expect(menu.x + menu.width).toBeLessThanOrEqual(width);
            expect(menu.y).toBeGreaterThanOrEqual(0);
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
            await page.screenshot({ path: testInfo.outputPath(`attachments-${width}-${theme}.png`), fullPage: true });
        }
    }
});
