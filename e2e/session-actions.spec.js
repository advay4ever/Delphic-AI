const { expect, test } = require("@playwright/test");

async function openMathTutor(page) {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
}

test("chat actions download and delete a selected past chat", async ({ page }) => {
    const browserErrors = [];
    page.on("pageerror", error => browserErrors.push(error.message));
    page.on("console", message => {
        if (message.type() === "error") browserErrors.push(message.text());
    });
    const prompt = `Graph y = x^2 - ${(4 + Math.random()).toFixed(4)}`;
    await openMathTutor(page);

    const graphRequest = await page.evaluate(async question => {
        const response = await fetch("/local-graph-message", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: question }),
        });
        return { ok: response.ok, status: response.status };
    }, prompt);
    expect(graphRequest).toEqual({ ok: true, status: 200 });
    await page.locator("#newChatBtn").click();

    const savedChat = page.locator(".session-list li", { hasText: prompt });
    await expect(savedChat).toBeVisible();
    const actionsTrigger = savedChat.locator(".session-actions-trigger");
    await actionsTrigger.click();

    const actionMenu = page.getByRole("menu", { name: `Actions for ${prompt}` });
    await expect(actionMenu.getByRole("menuitem", { name: "Download chat" })).toBeVisible();
    await expect(actionMenu.getByRole("menuitem", { name: "Delete chat" })).toBeVisible();

    const downloadPromise = page.waitForEvent("download");
    await actionMenu.getByRole("menuitem", { name: "Download chat" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^delphic-math-chat-.*\.html$/);
    expect(browserErrors).toEqual([]);

    await actionsTrigger.click();
    await page.getByRole("menuitem", { name: "Delete chat" }).click();
    const deleteDialog = page.getByRole("alertdialog", { name: "Delete this chat?" });
    await expect(deleteDialog).toBeVisible();
    await expect(deleteDialog).toContainText("This cannot be undone.");
    await deleteDialog.getByRole("button", { name: "Keep chat" }).click();
    await expect(deleteDialog).toBeHidden();
    await expect(savedChat).toBeVisible();

    await actionsTrigger.click();
    await page.getByRole("menuitem", { name: "Delete chat" }).click();
    await expect(deleteDialog).toBeVisible();
    await deleteDialog.getByRole("button", { name: "Delete chat" }).click();
    await expect(savedChat).toBeHidden();
});

test("manage chats selects and deletes several conversations together", async ({ page }) => {
    await openMathTutor(page);
    const prompts = [
        `Graph y = x + ${(10 + Math.random()).toFixed(4)}`,
        `Graph y = x^2 + ${(20 + Math.random()).toFixed(4)}`,
    ];

    for (const prompt of prompts) {
        const result = await page.evaluate(async question => {
            const response = await fetch("/local-graph-message", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: question }),
            });
            return response.ok;
        }, prompt);
        expect(result).toBe(true);
        await page.locator("#newChatBtn").click();
    }

    await page.getByRole("button", { name: "Manage" }).click();
    for (const prompt of prompts) {
        await page.getByRole("checkbox", { name: `Select ${prompt}` }).check();
    }
    const deleteSelected = page.getByRole("button", { name: "Delete (2)" });
    await expect(deleteSelected).toBeEnabled();
    await deleteSelected.click();

    const dialog = page.getByRole("alertdialog", { name: "Delete 2 chats?" });
    await expect(dialog).toContainText("selected conversations");
    await dialog.getByRole("button", { name: "Delete 2 chats" }).click();

    for (const prompt of prompts) {
        await expect(page.locator("#pastSessionsList", { hasText: prompt })).toBeHidden();
    }
});
