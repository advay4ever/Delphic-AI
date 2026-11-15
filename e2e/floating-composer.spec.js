const { expect, test } = require("@playwright/test");

test("the empty tutor starts clean and disappears with the first message", async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
    await page.route("**/history", route => route.fulfill({
        status: 200,
        json: { session_id: "math-session", messages: [], images: [], tokens_used: 0 },
    }));
    await page.route("**/stream", route => route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: [
            "data: Start by subtracting 3.\n\n",
            "event: complete\n",
            'data: {"tokens_used":1,"finish_reason":"complete","can_continue":false}\n\n',
            "data: [DONE:1]\n\n",
        ].join(""),
    }));

    await page.goto("/#tutor");
    const welcome = page.locator(".welcome-message");
    await expect(welcome).toBeVisible();
    await expect(welcome.locator("h2")).toHaveText("What are you working on?");
    const welcomeStyle = await welcome.locator(".tutor-welcome").evaluate(element => ({
        background: getComputedStyle(element).backgroundColor,
        borderTopWidth: getComputedStyle(element).borderTopWidth,
        boxShadow: getComputedStyle(element).boxShadow,
    }));
    expect(welcomeStyle.background).toBe("rgba(0, 0, 0, 0)");
    expect(welcomeStyle.borderTopWidth).toBe("0px");
    expect(welcomeStyle.boxShadow).toBe("none");
    await page.waitForTimeout(400);
    await page.screenshot({ path: "/tmp/delphic-demo-empty-state.png", fullPage: true });

    await page.locator("#userInput").fill("Solve 2x + 3 = 11");
    await page.locator("#sendBtn").click();
    await expect(welcome).toHaveCount(0);
    await expect(page.locator(".message.user").last()).toContainText("Solve 2x + 3 = 11");
});

test("the composer floats over the chat while the latest message remains readable", async ({ page }) => {
    const messages = [];
    for (let index = 1; index <= 12; index += 1) {
        messages.push({ id: index * 2 - 1, role: "user", content: `Question ${index}` });
        messages.push({
            id: index * 2,
            role: "assistant",
            content: `Answer ${index}: This longer response gives the scrolling area enough content to test the floating composer.`,
        });
    }

    await page.route("**/history", route => route.fulfill({
        status: 200,
        json: { session_id: "math-session", messages, images: [], tokens_used: 0 },
    }));
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
    await expect(page.locator(".message")).toHaveCount(messages.length);

    const layout = await page.evaluate(async () => {
        const chat = document.querySelector(".chat-main").getBoundingClientRect();
        const scroller = document.querySelector("#chatMessages");
        const scrollerRect = scroller.getBoundingClientRect();
        const composer = document.querySelector(".chat-input-area");
        const composerRect = composer.getBoundingClientRect();
        scroller.style.scrollBehavior = "auto";
        scroller.scrollTop = scroller.scrollHeight;
        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const lastMessageRect = document.querySelector(".message:last-child").getBoundingClientRect();
        const pillRect = document.querySelector(".text-pill").getBoundingClientRect();
        const composerStyle = getComputedStyle(composer);
        const scrollerStyle = getComputedStyle(scroller);
        return {
            composerPosition: composerStyle.position,
            composerBackground: composerStyle.backgroundColor,
            composerBottom: composerRect.bottom,
            chatBottom: chat.bottom,
            scrollerBottom: scrollerRect.bottom,
            clearance: Number.parseFloat(scrollerStyle.paddingBottom),
            composerHeight: composerRect.height,
            scrollerClientHeight: scroller.clientHeight,
            scrollerScrollHeight: scroller.scrollHeight,
            scrollerScrollTop: scroller.scrollTop,
            lastMessageBottom: lastMessageRect.bottom,
            pillTop: pillRect.top,
        };
    });

    expect(layout.composerPosition).toBe("absolute");
    expect(layout.composerBackground).toBe("rgba(0, 0, 0, 0)");
    expect(Math.abs(layout.composerBottom - layout.chatBottom)).toBeLessThan(2);
    expect(Math.abs(layout.scrollerBottom - layout.chatBottom)).toBeLessThan(2);
    expect(layout.clearance).toBeGreaterThanOrEqual(layout.composerHeight);
    expect(layout.scrollerClientHeight).toBeLessThan(layout.scrollerScrollHeight);
    expect(layout.scrollerScrollTop).toBeGreaterThan(0);
    expect(layout.lastMessageBottom).toBeLessThanOrEqual(layout.pillTop);
    await page.screenshot({ path: "/tmp/delphic-floating-composer.png", fullPage: true });
});
