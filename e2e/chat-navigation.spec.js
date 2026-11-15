const { test, expect } = require("@playwright/test");

function history(id, content = id) {
    return { session_id: id, messages: [{ id: 1, role: "user", content }], images: [], tokens_used: 0 };
}
async function setup(page) {
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
    await page.route("**/history", route => route.fulfill({ json: history("initial") }));
    await page.route("**/sessions", route => route.fulfill({ json: { current_session_id: "initial", sessions: [] } }));
    await page.goto("/#tutor");
    await expect(page.locator(".message.user")).toHaveText(/initial/);
}

for (const next of ["switch", "new"]) {
    test(`delayed A cannot replace a later ${next} choice`, async ({ page }) => {
        await setup(page);
        let release;
        const gate = new Promise(resolve => { release = resolve; });
        const calls = [];
        await page.route("**/sessions/switch", async route => {
            const id = route.request().postDataJSON().session_id;
            calls.push(id);
            if (id === "A") await gate;
            await route.fulfill({ json: history(id) });
        });
        await page.route("**/sessions/new", route => route.fulfill({ json: { session_id: "new-chat" } }));
        const started = page.waitForRequest(r => r.url().endsWith("/sessions/switch"));
        await page.evaluate(() => { void switchToSession("A"); });
        await started;
        await page.evaluate(next => { if (next === "new") void startNewChat(); else void switchToSession("B"); }, next);
        expect(calls).toEqual(["A"]);
        release();
        await expect.poll(() => page.evaluate(() => activeSessionId)).toBe(next === "new" ? "new-chat" : "B");
        await page.evaluate(() => chatNavigationTail);
        await expect(page.locator(".message.user").filter({ hasText: /^A/ })).toHaveCount(0);
        if (next === "switch") await expect(page.locator(".message.user")).toHaveText(/B/);
    });
}

test("a stale graph response cannot attach to the next conversation", async ({ page }) => {
    await setup(page);
    await page.route("**/sessions/switch", route => {
        const id = route.request().postDataJSON().session_id;
        return route.fulfill({ json: id === "A" ? { ...history("A", "Graph y=x^2"), messages: [
            { role: "user", content: "Graph y=x^2" }, { role: "assistant", content: "A graph reply" },
        ] } : history("B") });
    });
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route("**/plot", async route => {
        await gate;
        await route.fulfill({ json: { version: 1, kind: "function_2d", equation_latex: "x^2",
            viewport: { x_min: -10, x_max: 10, y_min: -10, y_max: 10 }, series: [] } }).catch(() => {});
    });
    const started = page.waitForRequest(r => r.url().endsWith("/plot"));
    await page.evaluate(() => { void switchToSession("A"); });
    await started;
    await page.evaluate(() => { void switchToSession("B"); });
    await expect(page.locator(".message.user")).toHaveText(/B/);
    release();
    await page.evaluate(() => chatNavigationTail);
    await expect(page.locator(".local-graph-container")).toHaveCount(0);
});

test("late initial history cannot overwrite New chat", async ({ page }) => {
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    await page.route("**/history", async route => { await gate; await route.fulfill({ json: history("old-history") }); });
    await page.route("**/sessions", route => route.fulfill({ json: { current_session_id: "new-chat", sessions: [] } }));
    await page.route("**/sessions/new", route => route.fulfill({ json: { session_id: "new-chat" } }));
    await page.goto("/#tutor");
    await page.locator("#newChatBtn").click();
    release();
    await expect.poll(() => page.evaluate(() => activeSessionId)).toBe("new-chat");
    await expect(page.locator(".message.user")).toHaveCount(0);
});

test("two real tabs keep their own question destinations and reload choices", async ({ context }) => {
    const a = await context.newPage();
    await a.goto("/#tutor");
    await expect.poll(() => a.evaluate(() => activeSessionId)).not.toBeNull();
    const idA = await a.evaluate(() => activeSessionId);
    const b = await context.newPage();
    await b.goto("/#tutor");
    await b.locator("#newChatBtn").click();
    await expect.poll(() => b.evaluate(() => activeSessionId)).not.toBe(idA);
    const idB = await b.evaluate(() => activeSessionId);
    for (const [page, text] of [[a, "Graph y=x+29"], [b, "Graph y=x+37"]]) {
        await page.locator("#userInput").fill(text);
        await page.locator("#sendBtn").click();
        await expect(page.locator(".local-graph-container canvas")).toBeVisible();
        await expect(page.locator("#sendBtn")).toBeEnabled();
    }
    for (const [id, text, forbidden] of [[idA, "29", "37"], [idB, "37", "29"]]) {
        const response = await context.request.get("/history", { headers: { "X-Delphic-Chat-ID": id } });
        const contents = (await response.json()).messages.map(m => m.content).join(" ");
        expect(contents).toContain(text);
        expect(contents).not.toContain(forbidden);
    }
    await a.reload();
    await expect(a.locator(".message.user")).toContainText("29");
    expect(await a.evaluate(() => activeSessionId)).toBe(idA);
    await context.request.post("/sessions/delete", { data: { session_id: idA }, headers: { "X-Delphic-Chat-ID": idB } });
    await a.reload();
    await expect.poll(() => a.evaluate(() => activeSessionId)).not.toBe(idA);
    expect(await a.evaluate(() => activeSessionId)).not.toBe(idB);
    await expect(a.locator(".message.user")).toHaveCount(0);
});
