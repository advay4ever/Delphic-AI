const { test, expect } = require("@playwright/test");

const math = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable.";
const science = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process.";

function examples() {
    return [
        { id: "algebra", title: "Balancing linear equations", subject: "math", text: math, enabled: 1 },
        { id: "plants", title: "Photosynthesis and plant cells", subject: "science", text: science, enabled: 0 },
        { id: "combined", title: "My class notebook", subject: "both", text: math + "\n\n" + science, enabled: 1 },
    ].map(note => ({ ...note, revision: 1, updated_at: "2026-11-03 12:00:00", created_at: "2026-11-01 12:00:00" }));
}

async function mockNotes(page, notes = examples()) {
    await page.route("**/library/notes", route => route.request().method() === "GET"
        ? route.fulfill({ json: { notes } }) : route.abort());
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 1 } }));
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
    await page.route(/\/(?:science\/)?(?:ask|stream)$/, route => route.abort());
}

for (const url of ["/#tutor", "/science"]) {
    test("saved notes have directly accessible independent previews in " + url, async ({ page }) => {
        await mockNotes(page);
        const writes = [];
        page.on("request", request => { if (request.method() !== "GET") writes.push(request.url()); });
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        const cards = page.locator("#studyLibraryList .library-note-card");
        await expect(cards).toHaveCount(3);
        for (const card of await cards.all()) {
            await expect(card.locator(".library-note-excerpt")).toBeVisible();
            await expect(card.locator(".library-preview-toggle")).toBeVisible();
            await expect(card.locator(".library-preview-toggle")).toHaveText("Preview note");
            await expect(card.locator(".library-preview-toggle")).toHaveAttribute("aria-label", /^Preview note: /);
            await expect(card.locator(".library-note-preview")).toBeHidden();
            const style = await card.evaluate(element => {
                const css = getComputedStyle(element);
                return { border: css.borderTopWidth, radius: css.borderRadius, background: css.backgroundColor };
            });
            expect(style.border).toBe("1px");
            expect(style.radius).toBe("8px");
            expect(style.background).not.toBe("rgba(0, 0, 0, 0)");
        }
        const first = page.locator('[data-note-id="algebra"]');
        const toggle = first.getByRole("button", { name: "Preview note: Balancing linear equations", exact: true });
        await toggle.focus();
        await page.keyboard.press("Enter");
        await expect(first.getByRole("region", { name: "Balancing linear equations", exact: true })).toBeVisible();
        await expect(first.locator(".library-note-preview p")).toHaveText(math);
        await expect(first.locator(".library-note-excerpt")).toBeHidden();
        await expect(first.locator(".library-preview-toggle")).toHaveAttribute("aria-expanded", "true");
        await expect(first.locator("input[type=checkbox]")).toBeChecked();
        await page.locator('[data-note-id="plants"] .library-preview-toggle').click();
        await expect(first.locator(".library-note-preview")).toBeVisible();
        await expect(page.locator('[data-note-id="plants"] .library-note-preview p')).toHaveText(science);
        await expect(page.locator(".library-action-menu:visible")).toHaveCount(0);
        await first.locator(".library-preview-toggle").focus();
        await page.keyboard.press("Space");
        await expect(first.locator(".library-note-preview")).toBeHidden();
        await expect(first.locator(".library-note-excerpt")).toBeVisible();
        await expect(first.locator(".library-preview-toggle")).toHaveAttribute("aria-expanded", "false");
        expect(writes).toEqual([]);
    });

    test("note boundaries and preview controls fit all screen sizes and themes in " + url, async ({ page }, testInfo) => {
        const notes = examples();
        notes[0].title = "Algebra".repeat(10);
        notes[0].text = (math + "\n\n").repeat(50);
        notes[1].title = "<img src=x onerror=alert(1)>";
        notes[1].text += " <script>window.untrustedNoteExecuted = true</script>";
        await mockNotes(page, notes);
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        const dialog = page.locator("#studyLibraryDialog");
        const first = page.locator('[data-note-id="algebra"]');
        for (const width of [320, 390, 820, 1280]) {
            await page.setViewportSize({ width, height: width === 820 ? 400 : 900 });
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
                await expect(dialog).toBeVisible();
                for (const card of await page.locator(".library-note-card").all()) {
                    const fits = await card.evaluate(element => element.scrollWidth <= element.clientWidth + 1);
                    expect(fits).toBe(true);
                    const footer = card.locator(".library-note-footer");
                    const selection = await footer.locator(".library-enabled").boundingBox();
                    const preview = await footer.locator(".library-preview-toggle").boundingBox();
                    expect(selection.height).toBeGreaterThanOrEqual(44);
                    expect(preview.height).toBeGreaterThanOrEqual(44);
                    const overlap = Math.min(selection.x + selection.width, preview.x + preview.width) > Math.max(selection.x, preview.x)
                        && Math.min(selection.y + selection.height, preview.y + preview.height) > Math.max(selection.y, preview.y);
                    expect(overlap).toBe(false);
                }
                expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
                await first.locator(".library-preview-toggle").click();
                await expect(first.locator(".library-note-preview")).toBeVisible();
                expect(await first.locator(".library-note-preview").evaluate(element => element.scrollTop)).toBe(0);
                if (width === 390 || width === 1280) {
                    await first.locator(".library-note-preview").scrollIntoViewIfNeeded();
                    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`preview-${width}-${theme}.png`) });
                }
                await first.locator(".library-note-preview").focus();
                await page.keyboard.press("End");
                await expect(first.locator(".library-note-preview")).toBeFocused();
                expect(await first.locator(".library-note-preview").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
                await first.locator(".library-preview-toggle").click();
                await expect(first.locator(".library-note-preview")).toBeHidden();
                if (width === 390 || width === 1280) {
                    await dialog.evaluate(element => { element.scrollTop = 0; });
                    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${width}-${theme}.png`) });
                }
            }
        }
        const unsafe = page.locator('[data-note-id="plants"]');
        await unsafe.locator(".library-preview-toggle").click();
        await expect(unsafe.locator(".library-note-preview")).toContainText("<script>");
        await expect(page.locator("#studyLibraryList img, #studyLibraryList script")).toHaveCount(0);
        expect(await page.evaluate(() => window.untrustedNoteExecuted)).toBeUndefined();
        expect(errors).toEqual([]);
    });

    test("filtering notes preserves an open preview without changing selection in " + url, async ({ page }) => {
        await mockNotes(page);
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        const card = page.locator('[data-note-id="algebra"]');
        await card.locator(".library-preview-toggle").click();
        await page.locator("#librarySearch").fill("plants");
        await expect(card).toBeHidden();
        await page.locator("#librarySearch").fill("");
        await expect(card.locator(".library-note-preview")).toBeVisible();
        await expect(card.locator("input[type=checkbox]")).toBeChecked();
    });
}
