const { expect, test } = require("@playwright/test");

async function openMathTutor(page) {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
}

test("desktop sidebar can be dragged or keyboard-resized and remembers the selected width", async ({ page }) => {
    await openMathTutor(page);
    const resizeHandle = page.locator("#sidebarResizeHandle");
    const sidebar = page.locator("#sidebar");
    await expect(resizeHandle).toBeVisible();
    await expect(page.locator("#downloadChatBtn")).toHaveCount(0);
    await expect(page.locator("#clearBtn")).toHaveCount(0);

    const originalWidth = await sidebar.evaluate(element => Math.round(element.getBoundingClientRect().width));
    const resizeHandleBox = await resizeHandle.boundingBox();
    expect(resizeHandleBox).not.toBeNull();
    await page.mouse.move(resizeHandleBox.x + 6, resizeHandleBox.y + 120);
    await page.mouse.down();
    await page.mouse.move(originalWidth + 60, resizeHandleBox.y + 120);
    await page.mouse.up();
    await expect(sidebar).toHaveCSS("width", `${originalWidth + 60}px`);

    await resizeHandle.focus();
    await resizeHandle.press("ArrowRight");
    await resizeHandle.press("ArrowRight");

    const resizedWidth = originalWidth + 84;
    await expect(resizeHandle).toHaveAttribute("aria-valuenow", String(resizedWidth));
    await expect(sidebar).toHaveCSS("width", `${resizedWidth}px`);

    await page.reload();
    await expect(page.locator("#sidebar")).toHaveCSS("width", `${resizedWidth}px`);

    await page.evaluate(() => localStorage.removeItem("delphic-sidebar-width"));
});

test("sidebar resize handle stays hidden on phones", async ({ browser }) => {
    const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
    });
    const page = await context.newPage();
    await openMathTutor(page);
    await expect(page.locator("#sidebarResizeHandle")).toBeHidden();
    await context.close();
});
