const { expect, test } = require("@playwright/test");

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
});

test("input warnings remain visible longer than the previous three-second timeout", async ({ page }) => {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();

    await page.locator("#userInput").fill("x".repeat(2_001));
    await page.locator("#sendBtn").click();

    const warning = page.locator(".input-warning");
    await expect(warning).toHaveText(/too long/i);
    await page.waitForTimeout(3_500);
    await expect(warning).toHaveText(/too long/i);
});

test("a one-character step answer is sent to the tutor", async ({ page }) => {
    let sentMessage = null;
    await page.route("**/stream", async route => {
        sentMessage = route.request().postDataJSON()?.message;
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
                "data: Correct.\n\n",
                "event: complete\n",
                'data: {"tokens_used":1,"finish_reason":"complete","can_continue":false}\n\n',
                "data: [DONE:1]\n\n",
            ].join(""),
        });
    });

    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
    await expect(page.locator(".welcome-message")).toBeVisible();
    await page.locator("#userInput").fill("4");
    await page.locator("#sendBtn").click();

    await expect.poll(() => sentMessage).toBe("4");
    await expect(page.locator(".welcome-message")).toHaveCount(0);
    await expect(page.locator(".message.user").last()).toContainText("4");
});
