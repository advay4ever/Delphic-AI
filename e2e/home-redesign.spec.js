const { test, expect } = require("@playwright/test");

async function mockWorkspace(page) {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "home-test", messages: [], images: [], tokens_used: 0,
    } }));
    await page.route("**/sessions", route => route.fulfill({ json: {
        current_session_id: "home-test", sessions: [],
    } }));
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 0 } }));
}

async function homeVisible(page) {
    await expect(page.locator("body")).toHaveClass(/home-active/);
    await expect(page.locator("#homeTitle")).toBeVisible();
    await expect(page.locator(".chat-main")).toBeHidden();
}

async function mathVisible(page) {
    await expect(page.locator("body")).not.toHaveClass(/home-active/);
    await expect(page.locator("#homePage")).toBeHidden();
    await expect(page.locator(".welcome-message h2")).toBeVisible();
    await expect(page.locator("#userInput")).toBeVisible();
}

async function readable(locator) {
    const contrast = await locator.evaluate(el => {
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d");
        const rgb = value => {
            context.clearRect(0, 0, 1, 1);
            context.fillStyle = value;
            context.fillRect(0, 0, 1, 1);
            const pixel = [...context.getImageData(0, 0, 1, 1).data];
            return [...pixel.slice(0, 3), pixel[3] / 255];
        };
        const style = getComputedStyle(el);
        const surface = rgb(getComputedStyle(el.closest(".home-page")).backgroundColor);
        const fill = rgb(style.backgroundColor);
        const alpha = fill[3] ?? 1;
        const background = surface.map((v, i) => fill[i] * alpha + v * (1 - alpha));
        const luminance = values => values.slice(0, 3).map(v => {
            const s = v / 255;
            return s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4;
        }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
        const a = luminance(rgb(style.color));
        const b = luminance(background);
        return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
}

for (const theme of ["light", "dark", "neon"]) {
    test(`Home ${theme} has readable, balanced entry points across screen sizes`, async ({ page }, testInfo) => {
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await mockWorkspace(page);
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.addInitScript(value => localStorage.setItem("math-tutor-theme", value), theme);
        for (const viewport of [
            { width: 1920, height: 1080 }, { width: 1440, height: 900 },
            { width: 1024, height: 768 }, { width: 768, height: 1024 },
            { width: 390, height: 844 }, { width: 320, height: 640 },
            { width: 320, height: 480 }, { width: 640, height: 360 },
        ]) {
            await page.setViewportSize(viewport);
            await page.goto("/");
            await page.mouse.move(0, 0);
            await homeVisible(page);
            await expect(page.locator("#homeTitle")).toHaveText("Delphic AI");
            await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
            const buttons = page.locator(".home-actions button");
            await expect(buttons).toHaveText(["Math tutor", "Science tutor"]);
            const math = await buttons.nth(0).boundingBox();
            const science = await buttons.nth(1).boundingBox();
            expect(math.y).toBe(science.y);
            expect(math.height).toBe(science.height);
            expect(math.height).toBeGreaterThanOrEqual(44);
            expect(math.x + math.width).toBeLessThan(science.x);
            expect(science.x + science.width).toBeLessThanOrEqual(viewport.width);
            expect(math.y + math.height).toBeLessThan(viewport.height);
            expect(await buttons.evaluateAll(items => items.every(el => el.scrollWidth <= el.clientWidth))).toBe(true);
            expect(await page.locator(".brand-mark img").evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true);
            await expect(buttons.locator("svg use")).toHaveCount(2);
            await expect(page.locator(".home-links a")).toHaveText(["Support", "Approach", "Workspace"]);
            const nextSection = await page.locator("#support").boundingBox();
            expect(nextSection.y).toBeLessThan(viewport.height - 12);
            await expect(page.locator("#support .section-kicker")).toBeInViewport({ ratio: 1 });
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
            for (const selector of ["#homeTitle", ".home-tagline", ".home-links a", ".home-signal-row", ".home-actions button", ".section-kicker", ".subject-lane p"]) {
                await readable(page.locator(selector).first());
            }
            for (const button of await buttons.all()) {
                await readable(button);
                await button.hover();
                await readable(button);
            }
            await page.mouse.move(0, 0);
            await page.screenshot({ path: testInfo.outputPath(`home-${theme}-${viewport.width}-${viewport.height}.png`) });
        }
        expect(errors).toEqual([]);
    });
}

for (const source of [".home-nav-actions", ".home-actions"]) {
    test(`Home ${source} entries, browser history, and reload select the correct tutor`, async ({ page }) => {
        await mockWorkspace(page);
        await page.goto("/");
        await page.locator(`${source} [data-start-tutor]`).click();
        await expect(page).toHaveURL(/\/#tutor$/);
        await mathVisible(page);
        await expect(page.locator("#userInput")).toBeFocused();
        await page.goBack();
        await homeVisible(page);
        await expect(page.locator(".home-actions [data-start-tutor]")).toBeFocused();
        await page.goForward();
        await mathVisible(page);
        await page.reload();
        await mathVisible(page);
        await page.locator('.sidebar-workspace a[href="/"]').click();
        await homeVisible(page);
        await page.locator(`${source} [data-start-science]`).click();
        await expect(page).toHaveURL(/\/science$/);
        await expect(page.locator(".welcome-message h2")).toBeVisible();
        await page.locator('.sidebar-workspace a[href="/"]').click();
        await homeVisible(page);
        await page.goBack();
        await expect(page).toHaveURL(/\/science$/);
        await page.locator('.sidebar-workspace a[href="/#tutor"]').click();
        await mathVisible(page);
    });
}

test("Home anchors remain Home on reload and enter Math without a page scroll offset", async ({ page }) => {
    await mockWorkspace(page);
    await page.goto("/");
    for (const [label, id] of [["Support", "support"], ["Approach", "approach"], ["Workspace", "workspace"]]) {
        await page.locator(".home-links").getByRole("link", { name: label }).click();
        await expect(page).toHaveURL(new RegExp(`#${id}$`));
        await homeVisible(page);
        await expect(page.locator(`#${id}`)).toBeInViewport();
        await page.reload();
        await homeVisible(page);
    }
    await expect(page.locator(".subject-lane")).toHaveCount(3);
    await expect(page.locator(".approach-item")).toHaveCount(3);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.locator(".home-actions [data-start-tutor]").evaluate(el => el.click());
    await mathVisible(page);
    expect(await page.evaluate(() => scrollY)).toBe(0);
    await expect(page.locator("#sendBtn")).toBeInViewport();
});

test("Same-document Home navigation preserves a Math draft, photo, and guided mode", async ({ page }) => {
    await mockWorkspace(page);
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
    await mathVisible(page);
    await page.locator("#userInput").fill("Please check my work on this equation");
    await page.locator("#stepByStepToggle").focus();
    await page.keyboard.press("Space");
    await page.locator("#attachmentPhotoInput").setInputFiles({
        name: "worksheet.png", mimeType: "image/png",
        buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKqWQAAAABJRU5ErkJggg==", "base64"),
    });
    await page.goBack();
    await homeVisible(page);
    await page.goForward();
    await mathVisible(page);
    await expect(page.locator("#userInput")).toHaveValue("Please check my work on this equation");
    await expect(page.locator("#stepByStepToggle")).toBeChecked();
    await expect(page.locator(".attachment-chip")).toBeVisible();
});

test("Settings theme choice also updates Home and survives reload", async ({ page }) => {
    await mockWorkspace(page);
    await page.goto("/#tutor");
    for (const theme of ["light", "neon", "dark"]) {
        await page.locator("#aiSettingsBtn").click();
        await page.locator("#themeToggle").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        await page.keyboard.press("Escape");
        await page.locator('.sidebar-workspace a[href="/"]').click();
        await homeVisible(page);
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.reload();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.locator(".home-actions [data-start-tutor]").click();
        await mathVisible(page);
    }
});

test("Home keyboard focus is visible and reduced motion removes button transitions", async ({ page }) => {
    await mockWorkspace(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").focus();
    await expect(page.locator(".home-actions [data-start-tutor]")).toHaveCSS("outline-style", "solid");
    await expect(page.locator(".home-actions [data-start-tutor]")).toHaveCSS("transition-duration", "0s");
    await page.keyboard.press("Tab");
    await expect(page.locator(".home-actions [data-start-science]")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/science$/);
});
