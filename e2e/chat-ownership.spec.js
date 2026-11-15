const { expect, test } = require("@playwright/test");

for (const mode of ["math", "science"]) {
    test(`${mode} chats are private between browser profiles and survive same-browser reload`, async ({ browser }) => {
        const owner = await browser.newContext();
        const stranger = await browser.newContext();
        try {
            const prefix = mode === "science" ? "/science" : "";
            const page = await owner.newPage();
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            // Both routes save a local result without contacting an AI provider.
            const saved = await owner.request.post(mode === "science" ? "/science/ask" : "/local-graph-message", {
                data: { message: "Graph y = x^2 + 0.375" },
            });
            expect(saved.status()).toBe(200);
            const history = await (await owner.request.get(prefix + "/history")).json();
            expect(history.messages).toHaveLength(2);
            const chat = history.session_id;
            await page.reload();
            await expect(page.locator(".message.user").filter({ hasText: "Graph y = x^2 + 0.375" })).toBeVisible();
            const nextTab = await owner.newPage();
            await nextTab.goto(mode === "science" ? "/science" : "/#tutor");
            await expect(nextTab.locator(".message.user").filter({ hasText: "Graph y = x^2 + 0.375" })).toBeVisible();

            const visitor = await stranger.newPage();
            await visitor.goto(mode === "science" ? "/science" : "/#tutor");
            const listing = await (await stranger.request.get(prefix + "/sessions")).json();
            expect(listing.sessions).toEqual([]);
            expect(listing.current_session_id).not.toBe(chat);
            await expect(visitor.locator(".message.user")).toHaveCount(0);
            for (const action of ["switch", "messages", "title", "delete", "delete-many"]) {
                const response = await stranger.request.post(prefix + "/sessions/" + action, {
                    data: action === "delete-many" ? { session_ids: [chat] } : { session_id: chat },
                });
                expect(response.status()).toBe(404);
                expect(await response.text()).not.toContain("0.375");
            }
            const download = await owner.request.post(prefix + "/sessions/messages", { data: { session_id: chat } });
            expect(download.status()).toBe(200);
            expect((await download.json()).messages).toHaveLength(2);
        } finally {
            await owner.close();
            await stranger.close();
        }
    });
}
