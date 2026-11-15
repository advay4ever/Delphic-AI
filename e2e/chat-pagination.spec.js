const { test, expect } = require("@playwright/test");
const messages = Array.from({ length: 65 }, (_, n) => ({ id: n + 1, role: "user", content: `Archive entry ${String(n + 1).padStart(3, "0")}` }));
function pageData(older = false) {
    return { session_id: "paged-chat", messages: older ? messages.slice(0, 25) : messages.slice(25),
        has_more: !older, next_before_id: older ? null : 26, snapshot_id: 65, total_messages: 65, images: [], tokens_used: 0 };
}
async function setup(page, prefix) {
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
    await page.route("**/history", route => route.fulfill({ json: pageData() }));
    await page.route("**/sessions", route => route.fulfill({ json: { current_session_id: "paged-chat", sessions: [
        { session_id: "paged-chat", preview: "Archive entries", message_count: 65 },
    ] } }));
    await page.route("**/sessions/messages", route => {
        const body = route.request().postDataJSON();
        if (body.before_id) expect(body.snapshot_id).toBe(65);
        return route.fulfill({ json: pageData(Boolean(body.before_id)) });
    });
    await page.goto(prefix || "/#tutor");
}

for (const prefix of ["", "/science"]) {
    test(`${prefix || "math"} older history is reachable and downloads include all 65 messages`, async ({ page }) => {
        await setup(page, prefix);
        await expect(page.locator(".message.user")).toHaveCount(40);
        await page.getByRole("button", { name: "Load earlier messages" }).click();
        await expect(page.locator(".message.user")).toHaveCount(65);
        await expect(page.locator(".message.user").first()).toContainText("Archive entry 001");
        await expect(page.locator("#loadEarlierMessages")).toHaveCount(0);
        const complete = await page.evaluate(() => loadCompleteTranscript("paged-chat"));
        expect(complete.messages.map(m => m.id)).toEqual(messages.map(m => m.id));
        const downloaded = page.waitForEvent("download");
        await page.evaluate(() => downloadSessionChat({ session_id: "paged-chat" }));
        expect((await downloaded).suggestedFilename()).toMatch(/\.html$/);
    });
}

test("oversized or interrupted exports fail explicitly instead of downloading a partial chat", async ({ page }) => {
    await setup(page, "");
    await page.route("**/sessions/messages", route => route.fulfill({ json: { ...pageData(), total_messages: 10001 } }));
    let error = await page.evaluate(() => loadCompleteTranscript("paged-chat").catch(error => error.message));
    expect(error).toContain("No partial file");
    await page.route("**/sessions/messages", route => route.fulfill({ json: route.request().postDataJSON().before_id
        ? { ...pageData(true), messages: [] } : pageData() }));
    error = await page.evaluate(() => loadCompleteTranscript("paged-chat").catch(error => error.message));
    expect(error).toContain("chat changed");
});
