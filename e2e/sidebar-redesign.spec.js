const { test, expect } = require("@playwright/test");

const longTitle = "Understanding quadratic equations and comparing several different approaches to factoring";

async function mockSidebar(page, mode) {
    const base = mode === "science" ? "/science" : "";
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
    await page.route(`**${base}/history`, route => route.fulfill({ json: {
        session_id: "current", messages: [], images: [], tokens_used: 12,
    } }));
    await page.route(`**${base}/sessions`, route => route.fulfill({ json: {
        current_session_id: "current",
        sessions: [
            { session_id: "current", preview: "Exploring a new topic", message_count: 2, title_generated: true },
            { session_id: "past", preview: longTitle, message_count: 2, title_generated: true },
            ...Array.from({ length: 25 }, (_, i) => ({
                session_id: `past-${i}`, preview: `Learning topic ${i + 1}`, message_count: 2, title_generated: true,
            })),
        ],
    } }));
}

for (const mode of ["math", "science"]) {
    for (const theme of ["light", "dark", "neon"]) {
        test(`${mode} sidebar groups navigation and tools in ${theme}`, async ({ page }) => {
            await mockSidebar(page, mode);
            await page.addInitScript(theme => localStorage.setItem("math-tutor-theme", theme), theme);
            const iconResponse = page.waitForResponse(response => response.url().includes("vendor/lucide/sidebar.svg"));
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            expect((await iconResponse).ok()).toBe(true);
            await expect(page.locator(".sidebar-header h2")).toHaveText("Delphic AI");
            await expect(page.locator(".sidebar-workspace .workspace-switch")).toHaveText(["Home", "Math tutor", "Science tutor"]);
            const selected = page.locator('.sidebar-workspace [aria-current="page"]');
            await expect(selected).toHaveText(mode === "math" ? "Math tutor" : "Science tutor");
            await expect(selected).toHaveCSS("background-color", "rgba(0, 0, 0, 0)");
            await expect(page.locator(".sidebar-tools #studyLibraryBtn")).toBeVisible();
            await expect(page.locator("#chatListHeading")).toHaveText("Recent chats");
            await expect(page.locator("#tokenCount")).toHaveText("12");
            await expect(page.locator("#newChatBtn")).toBeEnabled();
            await expect(page.locator(".sidebar-tools #competitionPicker")).toHaveCount(mode === "math" ? 1 : 0);

            const past = page.locator(".session-list-item").filter({ hasText: longTitle });
            await expect(past.locator(".session-open-btn")).toHaveAttribute("title", longTitle);
            await expect(past.locator(".sidebar-icon")).toHaveCount(1);
            await past.locator(".session-actions-trigger").focus();
            await page.keyboard.press("Enter");
            await expect(page.locator(".session-action-heading")).toHaveText(longTitle);
            await expect(page.getByRole("menuitem", { name: "Download chat" })).toBeVisible();
            await expect(page.getByRole("menuitem", { name: "Delete chat", exact: true })).toBeVisible();
            await page.keyboard.press("Escape");
            await expect(past.locator(".session-actions-trigger")).toBeFocused();

            const geometry = await page.locator("#sidebar").evaluate(sidebar => {
                const nav = sidebar.querySelector(".sidebar-nav");
                const list = sidebar.querySelector(".session-list");
                const footer = sidebar.querySelector(".sidebar-footer");
                return {
                    overflow: nav.scrollWidth > nav.clientWidth,
                    listScrolls: list.scrollHeight > list.clientHeight,
                    navBottom: nav.getBoundingClientRect().bottom,
                    footerTop: footer.getBoundingClientRect().top,
                };
            });
            expect(geometry.overflow).toBe(false);
            expect(geometry.listScrolls).toBe(true);
            expect(geometry.navBottom).toBeLessThanOrEqual(geometry.footerTop);
        });
    }

    for (const viewport of [{ width: 1024, height: 768 }, { width: 768, height: 1024 }, { width: 390, height: 844 }]) {
        test(`${mode} sidebar remains reachable at ${viewport.width}px`, async ({ browser }) => {
            const context = await browser.newContext({ viewport, hasTouch: true });
            const page = await context.newPage();
            await mockSidebar(page, mode);
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            if (viewport.width <= 768) await page.locator("#menuBtn").click();
            await expect(page.locator("#newChatBtn")).toBeInViewport();
            await expect(page.locator("#studyLibraryBtn")).toBeInViewport();
            await expect(page.locator(".workspace-home-link")).toBeInViewport();
            for (const link of await page.locator(".sidebar-workspace .workspace-switch").all()) {
                expect((await link.boundingBox()).height).toBeGreaterThanOrEqual(44);
            }
            const sidebar = page.locator("#sidebar");
            if (viewport.width <= 768) await expect(sidebar).toHaveCSS("transform", "matrix(1, 0, 0, 1, 0, 0)");
            const box = await sidebar.boundingBox();
            expect(box.x).toBeGreaterThanOrEqual(-1);
            expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
            const overflow = await page.locator(".sidebar-nav").evaluate(element => element.scrollWidth > element.clientWidth);
            expect(overflow).toBe(false);
            await page.locator("#studyLibraryBtn").click();
            await expect(page.locator("#studyLibraryDialog")).toBeVisible();
            await page.locator("#closeStudyLibrary").click();
            if (mode === "math") {
                if (viewport.width <= 768) await page.locator("#menuBtn").click();
                await page.locator("#competitionPracticeBtn").click();
                await expect(page.getByRole("menuitem", { name: "AMC 12", exact: true })).toBeVisible();
                await expect(page.getByRole("menuitem", { name: "Other competition" })).toBeInViewport();
                await page.keyboard.press("Escape");
            }
            await context.close();
        });
    }

    test(`${mode} supports narrow widths and keeps the last chat menu onscreen`, async ({ page }) => {
        await mockSidebar(page, mode);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        const handle = page.locator("#sidebarResizeHandle");
        await handle.focus();
        await page.keyboard.press("Home");
        await expect(page.locator("#sidebar")).toHaveCSS("width", "220px");
        await expect(page.locator("#studyLibraryBtn")).toBeVisible();
        expect(await page.locator(".sidebar-nav").evaluate(el => el.scrollWidth > el.clientWidth)).toBe(false);
        const trigger = page.locator(".session-list-item").last().locator(".session-actions-trigger");
        await trigger.scrollIntoViewIfNeeded();
        await trigger.click();
        const menu = page.locator(".session-action-menu");
        await expect(menu).toBeVisible();
        const menuBox = await menu.boundingBox();
        expect(menuBox.y).toBeGreaterThanOrEqual(0);
        expect(menuBox.y + menuBox.height).toBeLessThanOrEqual(page.viewportSize().height);
        await expect(page.getByRole("menuitem", { name: "Delete chat", exact: true })).toBeInViewport();
        await page.keyboard.press("Escape");
        await handle.focus();
        await page.keyboard.press("End");
        await expect(page.locator("#sidebar")).toHaveCSS("width", "420px");
    });
}

test("sidebar links lead directly to both tutors and back home", async ({ page }) => {
    await mockSidebar(page, "math");
    await mockSidebar(page, "science");
    await page.goto("/#tutor");
    await page.locator(".sidebar-workspace .tutor-link-science").click();
    await expect(page).toHaveURL(/\/science$/);
    await expect(page.locator("body")).toHaveAttribute("data-tutor-mode", "science");
    await page.locator(".sidebar-workspace .tutor-link-math").click();
    await expect(page).toHaveURL(/\/#tutor$/);
    await expect(page.locator("body")).not.toHaveClass(/home-active/);
    await expect(page.locator("#userInput")).toBeVisible();
    await page.locator(".sidebar-workspace .workspace-home-link").click();
    await expect(page.locator("#homePage")).toBeVisible();
});
