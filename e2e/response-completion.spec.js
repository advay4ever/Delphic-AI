const { expect, test } = require("@playwright/test");

const configuredAiSettings = {
    configured: true,
    provider: "groq",
    model: "openai/gpt-oss-120b",
    source: "test",
    providers: [],
};

async function openMathTutorWithMockedAi(page) {
    await page.route("**/ai-settings", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(configuredAiSettings),
        });
    });
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
}

test("structured completion metadata finalizes a response without appearing in the chat", async ({ page }) => {
    const browserErrors = [];
    let continuationRequest = null;
    page.on("pageerror", error => browserErrors.push(error.message));
    await openMathTutorWithMockedAi(page);

    await page.route("**/stream", async route => {
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
                "data: A deliberately partial answer.\n\n",
                "event: complete\n",
                'data: {"tokens_used":14,"finish_reason":"length","message_id":17,"session_id":"test-chat","can_continue":true,"continuation_count":0}\n\n',
                "data: [DONE:14]\n\n",
            ].join(""),
        });
    });
    await page.route("**/responses/continue", async route => {
        continuationRequest = route.request().postDataJSON();
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                reply: "A deliberately partial answer. Here is the completed explanation with \\(x^2\\).",
                tokens_used: 26,
                finish_reason: "complete",
                message_id: 17,
                session_id: "test-chat",
                can_continue: false,
                continuation_count: 1,
            }),
        });
    });

    await page.locator("#userInput").fill("Explain a long calculus problem");
    await page.locator("#sendBtn").click();

    const reply = page.locator(".message.assistant").last();
    await expect(reply.locator(".message-text")).toContainText("A deliberately partial answer.");
    await expect(reply).toHaveAttribute("data-finish-reason", "length");
    await expect(reply.locator(".copy-btn")).toBeVisible();
    await expect(page.locator("#chatMessages")).not.toContainText("finish_reason");
    await reply.getByRole("button", { name: "Continue response" }).click();
    await expect(reply.locator(".message-content")).toContainText("completed explanation");
    await expect(reply.locator(".katex")).toBeVisible();
    await expect(reply.getByText("Response completed", { exact: true })).toBeVisible();
    await expect(reply.locator(".continue-response-btn")).toHaveCount(0);
    expect(continuationRequest).toEqual({ message_id: 17, session_id: "test-chat" });
    expect(browserErrors).toEqual([]);
});

test("the legacy completion marker still finalizes a response", async ({ page }) => {
    await openMathTutorWithMockedAi(page);

    await page.route("**/stream", async route => {
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: "data: Legacy response works.\n\ndata: [DONE:9]\n\n",
        });
    });

    await page.locator("#userInput").fill("Explain a geometry idea");
    await page.locator("#sendBtn").click();

    const reply = page.locator(".message.assistant").last();
    await expect(reply.locator(".message-text")).toContainText("Legacy response works.");
    await expect(reply).toHaveAttribute("data-finish-reason", "unknown");
    await expect(reply.locator(".copy-btn")).toBeVisible();
});

test("a saved unfinished response offers continuation again after refresh", async ({ page }) => {
    await page.route("**/ai-settings", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(configuredAiSettings),
        });
    });
    await page.route("**/history", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                session_id: "saved-chat",
                tokens_used: 30,
                messages: [
                    { id: 20, role: "user", content: "Give a long explanation." },
                    {
                        id: 21,
                        role: "assistant",
                        content: "This saved response was cut off",
                        finish_reason: "length",
                        continuation_count: 0,
                        can_continue: true,
                    },
                    {
                        id: 22,
                        role: "assistant",
                        content: "This response finished normally.",
                        finish_reason: "complete",
                        continuation_count: 0,
                        can_continue: false,
                    },
                ],
            }),
        });
    });

    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();

    const replies = page.locator(".message.assistant");
    await expect(replies.nth(0).getByRole("button", { name: "Continue response" })).toBeVisible();
    await expect(replies.nth(1).locator(".continue-response-btn")).toHaveCount(0);
});

test("a failed continuation becomes a retry without changing the answer", async ({ page }) => {
    await openMathTutorWithMockedAi(page);
    await page.route("**/stream", async route => {
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
                "data: Keep this partial answer.\n\n",
                "event: complete\n",
                'data: {"tokens_used":8,"finish_reason":"length","message_id":31,"session_id":"retry-chat","can_continue":true,"continuation_count":0}\n\n',
            ].join(""),
        });
    });
    await page.route("**/responses/continue", async route => {
        await route.fulfill({
            status: 502,
            contentType: "application/json",
            body: JSON.stringify({ error: "The AI provider could not continue this response. Please try again." }),
        });
    });

    await page.locator("#userInput").fill("Explain this difficult proof");
    await page.locator("#sendBtn").click();
    const reply = page.locator(".message.assistant").last();
    await reply.getByRole("button", { name: "Continue response" }).click();

    await expect(reply.getByRole("button", { name: "Retry continuation" })).toBeEnabled();
    await expect(reply.locator(".message-content")).toContainText("Keep this partial answer.");
    await expect(page.locator(".input-warning")).toContainText("could not continue");
});

test("the continuation control fits a phone screen in every theme", async ({ browser }) => {
    const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
    });
    const page = await context.newPage();
    await page.route("**/ai-settings", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(configuredAiSettings),
        });
    });
    await page.route("**/history", async route => {
        await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                session_id: "phone-chat",
                tokens_used: 10,
                messages: [{
                    id: 41,
                    role: "assistant",
                    content: "This longer response needs another part.",
                    finish_reason: "length",
                    continuation_count: 0,
                    can_continue: true,
                }],
            }),
        });
    });

    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
    const continueButton = page.getByRole("button", { name: "Continue response" });
    await expect(continueButton).toBeVisible();

    for (const theme of ["light", "dark", "neon"]) {
        await page.locator("#aiSettingsBtn").click();
        await page.locator("#themeToggle").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.keyboard.press("Escape");
        const box = await continueButton.boundingBox();
        expect(box).not.toBeNull();
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(390);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
});
