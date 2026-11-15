const { test, expect } = require("@playwright/test");

const untrustedMath = String.raw`Safe math: \(x^2 + 1\).
\(\href{javascript:window.__mathSecurityMarker=1}{Untrusted link}\)
\(\includegraphics{https://example.invalid/math-security-probe.png}\)`;

for (const path of ["/#tutor", "/science"]) {
    test(`${path} blocks trusted LaTeX commands in history, updates, and downloads`, async ({ page }) => {
        const outbound = [];
        await page.route("https://example.invalid/**", route => {
            outbound.push(route.request().url());
            return route.abort();
        });
        await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
        await page.route("**/history", route => route.fulfill({ json: {
            session_id: "math-security-test", images: [],
            messages: [{ id: 1, role: "assistant", content: untrustedMath, finish_reason: "complete" }],
        } }));
        await page.route("**/sessions", route => route.fulfill({ json: {
            current_session_id: "math-security-test", sessions: [],
        } }));
        await page.goto(path);
        const reply = page.locator(".message.assistant").last();
        await expect(reply.locator(".katex")).not.toHaveCount(0);
        await expect(reply.locator("a, img")).toHaveCount(0);
        await page.evaluate(content => {
            window.__mathSecurityMarker = 0;
            updateAssistantMessageContent(document.querySelector(".message.assistant"), content);
        }, untrustedMath);
        await expect(reply.locator("a, img")).toHaveCount(0);
        const exported = await page.evaluate(content => {
            const container = document.createElement("div");
            container.innerHTML = renderTranscriptAssistantBody(content);
            return { unsafeElements: container.querySelectorAll("a, img").length,
                hasMath: Boolean(container.querySelector("math")), marker: window.__mathSecurityMarker };
        }, untrustedMath);
        expect(exported).toEqual({ unsafeElements: 0, hasMath: true, marker: 0 });
        expect(outbound).toEqual([]);
    });

    test(`${path} also blocks trusted commands in streamed answers`, async ({ page }) => {
        const outbound = [];
        await page.route("https://example.invalid/**", route => {
            outbound.push(route.request().url());
            return route.abort();
        });
        await page.route("**/ai-settings", route => route.fulfill({ json: {
            configured: true, provider: "groq", providers: [],
        } }));
        await page.route("**/history", route => route.fulfill({ json: {
            session_id: "math-security-test", messages: [], images: [],
        } }));
        await page.route("**/sessions", route => route.fulfill({ json: {
            current_session_id: "math-security-test", sessions: [],
        } }));
        await page.route("**/stream", route => route.fulfill({
            contentType: "text/event-stream",
            body: `event: token\ndata: ${JSON.stringify({ text: untrustedMath })}\n\n`
                + 'event: complete\ndata: {"finish_reason":"complete","tokens_used":0}\n\n',
        }));
        await page.goto(path);
        await page.locator("#userInput").fill("Explain this expression");
        await page.locator("#sendBtn").click();
        const reply = page.locator(".message.assistant").last();
        await expect(reply).toHaveAttribute("data-finish-reason", "complete");
        await expect(reply.locator(".katex")).not.toHaveCount(0);
        await expect(reply.locator("a, img")).toHaveCount(0);
        expect(outbound).toEqual([]);
    });
}
