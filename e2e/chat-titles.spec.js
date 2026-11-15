const { test, expect } = require("@playwright/test");

for (const [mode, switchBeforeTitle] of [
    ["math", false], ["math", true], ["science", false], ["science", true],
]) {
    test(`${mode} summarizes titles ${switchBeforeTitle ? "after switching chats" : "in the current chat"}`, async ({ page }) => {
        const base = mode === "science" ? "/science" : "";
        const firstId = mode === "science" ? "science:first" : "first";
        const newId = mode === "science" ? "science:new" : "new";
        let activeId = firstId;
        let hasAnswer = false;
        let generatedTitle = false;
        let titleCount = 0;
        let finishTitle;
        let titleStarted;
        const pendingTitle = new Promise(resolve => { titleStarted = resolve; });
        const titleRelease = new Promise(resolve => { finishTitle = resolve; });

        await page.route("**/ai-settings", route => route.fulfill({ json: {
            configured: true, provider: "groq", model: "test",
            providers: [{ id: "groq", label: "Groq", models: [{ id: "test", label: "Test" }] }],
        } }));
        await page.route(`**${base}/history`, route => route.fulfill({ json: {
            session_id: firstId, messages: [], images: [], tokens_used: 0,
        } }));
        await page.route(`**${base}/sessions`, route => route.fulfill({ json: {
            current_session_id: activeId,
            sessions: hasAnswer ? [{
                session_id: firstId,
                preview: generatedTitle ? "Understanding Positive Correlation" : "Why do scatter plot points go up?",
                title_generated: generatedTitle, title_ready: true, message_count: 2,
            }] : [],
        } }));
        await page.route(`**${base}/stream`, route => {
            hasAnswer = true;
            return route.fulfill({ contentType: "text/event-stream", body:
                'data: This is positive correlation.\n\nevent: complete\ndata: {"tokens_used":10,"finish_reason":"complete"}\n\n',
            });
        });
        await page.route(`**${base}/sessions/title`, async route => {
            titleCount++;
            expect(route.request().postDataJSON()).toEqual({ session_id: firstId });
            titleStarted();
            await titleRelease;
            generatedTitle = true;
            await route.fulfill({ json: {
                session_id: firstId, title: "Understanding Positive Correlation", title_generated: true, tokens_used: 25,
            } });
        });
        await page.route(`**${base}/sessions/new`, route => {
            activeId = newId;
            return route.fulfill({ json: { session_id: newId } });
        });

        await page.goto(base || "/#tutor");
        await expect(page.locator("#aiSettingsBtn")).toHaveText("Settings");
        await expect(page.locator("#aiSettingsBtn")).toHaveAttribute("data-configured", "true");
        await page.locator("#userInput").fill("Why do scatter plot points go up?");
        await page.locator("#sendBtn").click();
        await pendingTitle;
        await expect(page.locator(".message.assistant").last()).toContainText("This is positive correlation.");
        await expect(page.locator("#sendBtn")).toBeEnabled();
        if (switchBeforeTitle) {
            await page.locator("#newChatBtn").click();
            await expect(page.locator("#currentSessionPreview")).toHaveText("New conversation");
        }
        finishTitle();
        if (switchBeforeTitle) {
            await expect(page.locator("#pastSessionsList")).toContainText("Understanding Positive Correlation");
            await expect(page.locator("#currentSessionPreview")).toHaveText("New conversation");
            await expect(page.locator("#tokenCount")).toHaveText("0");
        } else {
            await expect(page.locator("#currentSessionPreview")).toHaveText("Understanding Positive Correlation");
            await expect(page.locator("#tokenCount")).toHaveText("25");
            await page.reload();
            await expect(page.locator("#currentSessionPreview")).toHaveText("Understanding Positive Correlation");
        }
        expect(titleCount).toBe(1);
    });
}
