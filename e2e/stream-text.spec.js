const { test, expect } = require("@playwright/test");

for (const path of ["/#tutor", "/science"]) {
    test(`${path} labels a provider timeout as interrupted and enables sending again`, async ({ page }) => {
        await page.route("**/ai-settings", r => r.fulfill({ json: { configured: true, provider: "groq", providers: [] } }));
        await page.route("**/stream", r => r.fulfill({ contentType: "text/event-stream", body:
            'event: token\ndata: {"text":"A partial explanation."}\n\nevent: complete\ndata: {"finish_reason":"error","tokens_used":0}\n\n' }));
        await page.goto(path);
        await page.locator("#userInput").fill("Explain this lesson");
        await page.locator("#sendBtn").click();
        const reply = page.locator(".message.assistant").last();
        await expect(reply).toHaveAttribute("data-finish-reason", "error");
        await expect(reply.locator(".response-status")).toContainText("Response interrupted");
        await expect(reply.locator(".message-text")).toContainText("A partial explanation");
        await page.locator("#userInput").fill("Try again");
        await expect(page.locator("#sendBtn")).toBeEnabled();
    });

    test(`${path} preserves split LaTeX, newlines, copy, and saved history`, async ({ page }) => {
        const slash = String.fromCharCode(92);
        const text = `Frequency ${slash}(${slash}nu=5${slash}).\n\nCompare ${slash}(a${slash}neq b${slash}) and ${slash}(${slash}nabla f${slash}).\nPath: \`C:${slash}notes${slash}new.txt\``;
        await page.route("**/ai-settings", r => r.fulfill({ json: { configured: true, provider: "groq", providers: [] } }));
        await page.route("**/history", r => r.fulfill({ json: { session_id: "stream-test", messages: [], images: [] } }));
        await page.route("**/sessions", r => r.fulfill({ json: { current_session_id: "stream-test", sessions: [] } }));
        const pieces = Array.from(text);
        const body = pieces.map(text => "event: token\r\ndata: " + JSON.stringify({ text }) + "\r\n\r\n").join("")
            + 'event: complete\r\ndata: {"finish_reason":"complete","tokens_used":0}';
        await page.addInitScript(body => {
            const original = window.fetch.bind(window);
            window.fetch = (...args) => {
                if (!String(args[0]).endsWith("/stream")) return original(...args);
                const bytes = new TextEncoder().encode(body);
                return Promise.resolve(new Response(new ReadableStream({ start(controller) {
                    for (let i = 0; i < bytes.length; i += 3) controller.enqueue(bytes.slice(i, i + 3));
                    controller.close();
                } }), { headers: { "Content-Type": "text/event-stream" } }));
            };
            Object.defineProperty(navigator, "clipboard", { value: { writeText: async text => { window.copied = text; } } });
        }, body);
        await page.goto(path);
        await page.locator("#userInput").fill("Explain frequency");
        await page.locator("#sendBtn").click();
        const reply = page.locator(".message.assistant").last();
        await expect(reply).toHaveAttribute("data-finish-reason", "complete");
        await expect(reply).toHaveAttribute("data-raw-content", text);
        await expect(reply.locator(".katex-error")).toHaveCount(0);
        await expect(reply.locator(".katex")).toHaveCount(3);
        await reply.locator(".copy-btn").click();
        await expect.poll(() => page.evaluate(() => window.copied)).toBe(text);
        await page.route("**/history", r => r.fulfill({ json: { session_id: "stream-test", messages: [
            { id: 1, role: "assistant", content: text, finish_reason: "complete" },
        ], images: [] } }));
        await page.reload();
        await expect(page.locator(".message.assistant").last()).toHaveAttribute("data-raw-content", text);
        await expect(page.locator(".katex-error")).toHaveCount(0);
    });
}
