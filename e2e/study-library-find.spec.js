const { test, expect } = require("@playwright/test");
const { showAddForm, showLibraryList } = require("./helpers/study-library");

const math = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable.";
const science = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process.";
const rows = page => page.locator("#studyLibraryList > li[data-note-id]:visible");
const names = page => rows(page).locator(".library-note-heading strong");

function examples() {
    return [
        { id: "one", title: "Zeta equations", subject: "math", text: math, enabled: 1, updated_at: "2026-10-13 12:00:00.000" },
        { id: "two", title: "Plant cells", subject: "science", text: science, enabled: 1, updated_at: "2026-10-16 12:00:00.000" },
        { id: "three", title: "Beta combined", subject: "both", text: math + science, enabled: 0, updated_at: "2026-10-15 12:00:00.000" },
        { id: "four", title: "alpha equations", subject: "math", text: math + " Algebra notebook: ecuaci\u00f3n.", enabled: 0, updated_at: "2026-10-14 12:00:00.000" },
    ].map(note => ({ ...note, created_at: "2026-10-01 00:00:00", revision: 1 }));
}

async function mockNotes(page, notes = examples()) {
    await page.route("**/library/notes", route => route.request().method() === "GET"
        ? route.fulfill({ json: { notes } }) : route.abort());
    await page.route("**/library/status?*", route => {
        const subject = new URL(route.request().url()).searchParams.get("subject");
        return route.fulfill({ json: { enabled_count: notes.filter(note => note.enabled && [subject, "both"].includes(note.subject)).length } });
    });
}

async function save(page, title, text = math, subject = "math", enabled = true) {
    const response = await page.request.post("/library/notes", { data: { title, text, subject, enabled } });
    expect(response.status()).toBe(201);
    return (await response.json()).id;
}

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, provider: "groq", providers: [] } }));
    await page.route(/\/(?:science\/)?(?:ask|stream)$/, route => route.abort());
});

for (const url of ["/#tutor", "/science"]) {
    test("search and exact subject filters stay local and never change selections in " + url, async ({ page }) => {
        await mockNotes(page);
        const mutations = [];
        page.on("request", request => { if (request.method() !== "GET") mutations.push(request.url()); });
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        await expect(names(page)).toHaveText(["Plant cells", "Beta combined", "alpha equations", "Zeta equations"]);
        await expect(page.locator("#libraryResultCount")).toHaveText("4 saved notes");
        await expect(rows(page).locator(".library-selection-state")).toHaveText(["On", "Off", "Off", "On"]);
        const other = url === "/science" ? "one" : "two";
        await expect(page.locator('[data-note-id="' + other + '"] .library-subject-hint')).toBeVisible();
        await expect(rows(page).filter({ hasText: "Beta combined" }).locator(".library-subject-hint")).toBeHidden();
        await page.getByLabel("Search notes", { exact: true }).fill("BALANCED");
        await expect(rows(page)).toHaveCount(3);
        await page.locator("#libraryFilterSubject").selectOption("math");
        await expect(names(page)).toHaveText(["alpha equations", "Zeta equations"]);
        await page.getByLabel("Search notes", { exact: true }).fill("ecuacio\u0301n");
        await expect(names(page)).toHaveText(["alpha equations"]);
        await page.getByLabel("Search notes", { exact: true }).fill("plant cells");
        await expect(rows(page)).toHaveCount(0);
        await expect(page.locator(".library-empty")).toHaveText("No matching notes.");
        await expect(page.getByRole("button", { name: "Add note", exact: true })).toBeVisible();
        await expect(page.locator("#libraryResultCount")).toHaveText("0 of 4 notes");
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await expect(page.locator("#librarySearch")).toBeFocused();
        await expect(rows(page)).toHaveCount(4);
        await page.locator("#libraryFilterSubject").selectOption("both");
        await expect(names(page)).toHaveText(["Beta combined"]);
        await expect(rows(page).getByRole("checkbox")).not.toBeChecked();
        await page.getByRole("button", { name: "Clear filters", exact: true }).click();
        await page.getByRole("combobox", { name: "Sort by", exact: true }).selectOption("title");
        await expect(names(page)).toHaveText(["alpha equations", "Beta combined", "Plant cells", "Zeta equations"]);
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
        expect(mutations).toEqual([]);
    });
}

test("filters preserve add and rename drafts and edited notes can leave the results safely", async ({ page }) => {
    await page.goto("/#tutor");
    const id = await save(page, "Algebra");
    await save(page, "Plants", science, "science");
    await page.locator("#studyLibraryBtn").click();
    await showAddForm(page);
    await page.locator("#studyLibraryNoteTitle").fill("Unsent draft");
    await page.locator("#studyLibraryText").fill(math + " My draft.");
    await showLibraryList(page);
    await page.locator("#librarySearch").fill("Algebra");
    await page.getByRole("button", { name: "Actions for Algebra", exact: true }).click();
    await page.getByRole("menuitem", { name: "Rename", exact: true }).click();
    await page.locator(".library-rename-form input:visible").fill("Geometry");
    await page.locator("#librarySearch").fill("Plants");
    await page.locator("#librarySearch").fill("Algebra");
    await expect(page.locator(".library-rename-form input:visible")).toHaveValue("Geometry");
    await page.getByRole("button", { name: "Save title", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note renamed.");
    await expect(page.locator(".library-empty")).toHaveText("No matching notes.");
    await expect(page.locator("#librarySearch")).toBeFocused();
    await page.getByRole("button", { name: "Clear filters", exact: true }).click();
    await page.locator("#libraryFilterSubject").selectOption("math");
    await page.getByRole("button", { name: "Actions for Geometry", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await expect(page.locator("#libraryBrowse")).toBeHidden();
    await page.locator("#libraryEditText").fill(science);
    await page.locator("#libraryEditSubject").selectOption("science");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note updated.");
    await expect(page.locator(".library-empty")).toHaveText("No matching notes.");
    await expect(page.locator("#librarySearch")).toBeFocused();
    await page.getByRole("button", { name: "Clear filters", exact: true }).click();
    await expect(names(page).first()).toHaveText("Geometry");
    await showAddForm(page);
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("Unsent draft");
    await expect(page.locator("#studyLibraryText")).toHaveValue(math + " My draft.");
    const saved = (await (await page.request.get("/library/notes")).json()).notes.find(note => note.id === id);
    expect(saved.subject).toBe("science");
    expect(saved.enabled).toBe(1);
});

test("deleting the only match leaves other saved notes and reset filters intact", async ({ page }) => {
    await page.goto("/#tutor");
    await save(page, "Algebra");
    await save(page, "Plants", science, "science");
    await page.locator("#studyLibraryBtn").click();
    await page.locator("#librarySearch").fill("Algebra");
    await page.getByRole("button", { name: "Actions for Algebra", exact: true }).click();
    await page.getByRole("menuitem", { name: "Delete", exact: true }).click();
    await page.getByRole("menuitem", { name: "Confirm delete", exact: true }).click();
    await expect(page.locator(".library-empty")).toHaveText("No matching notes.");
    await expect(page.getByRole("button", { name: "Add note", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Clear filters", exact: true }).click();
    await expect(names(page)).toHaveText(["Plants"]);
});

test("identical text gives an advisory but students may save a copy", async ({ page }) => {
    await page.goto("/#tutor");
    await save(page, "<img src=x> Algebra", math, "math", false);
    await page.locator("#studyLibraryBtn").click();
    await page.getByRole("button", { name: "Actions for <img src=x> Algebra", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await expect(page.locator("#libraryEditDuplicate")).toBeHidden();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await showAddForm(page);
    await page.locator("#studyLibraryNoteTitle").fill("My copy");
    await page.locator("#studyLibraryText").fill(math);
    await expect(page.locator("#libraryAddDuplicate")).toContainText('already saved as "<img src=x> Algebra"');
    await expect(page.locator("#libraryAddDuplicate img")).toHaveCount(0);
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
    await expect(rows(page)).toHaveCount(2);
    await page.getByRole("button", { name: "Actions for My copy", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await expect(page.locator("#libraryEditDuplicate")).toBeVisible();
    await page.locator("#libraryEditText").fill(math + " A different example.");
    await expect(page.locator("#libraryEditDuplicate")).toBeHidden();
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Discard changes", exact: true }).click();
});

test("a fifty-note library is searchable by text without a provider request", async ({ page }) => {
    const notes = Array.from({ length: 50 }, (_, i) => ({ ...examples()[0], id: "note-" + i,
        title: "Chapter " + (i + 1), text: math + " Example marker" + i }));
    await mockNotes(page, notes);
    await page.goto("/#tutor");
    await page.locator("#studyLibraryBtn").click();
    await expect(rows(page)).toHaveCount(50);
    await page.locator("#librarySort").selectOption("title");
    await expect(names(page).nth(1)).toHaveText("Chapter 2");
    await page.locator("#librarySearch").fill("marker49");
    await expect(names(page)).toHaveText(["Chapter 50"]);
    await expect(page.locator("#libraryResultCount")).toHaveText("1 of 50 notes");
});

test("note menus survive focus scrolling but close when their anchor actually moves", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 400 });
    await mockNotes(page);
    await page.goto("/#tutor");
    await page.locator("#studyLibraryBtn").click();
    const trigger = page.getByRole("button", { name: "Actions for Zeta equations", exact: true });
    await expect(trigger).toBeEnabled();
    await trigger.focus();
    await page.keyboard.press("ArrowUp");
    await expect(page.getByRole("menuitem", { name: "Delete", exact: true })).toBeFocused();
    const dialog = page.locator("#studyLibraryDialog");
    const scrollTop = await dialog.evaluate(el => el.scrollTop);
    await page.locator("#closeStudyLibrary").click({ trial: true });
    expect(await dialog.evaluate(el => el.scrollTop)).toBe(scrollTop);
    await page.keyboard.press("Home");
    await expect(page.getByRole("menuitem", { name: "Preview", exact: true })).toBeFocused();
    await dialog.evaluate(el => { el.scrollTop = 0; });
    await expect(page.locator(".library-action-menu:visible")).toHaveCount(0);
    await expect(trigger).toBeFocused();
    expect(await dialog.evaluate(el => el.scrollTop)).toBe(0);
});

for (const device of [
    { name: "computer", viewport: { width: 1280, height: 900 }, hasTouch: false },
    { name: "iPad portrait simulation", viewport: { width: 820, height: 1180 }, hasTouch: true },
    { name: "iPad landscape simulation", viewport: { width: 1180, height: 820 }, hasTouch: true },
]) {
    test.describe(device.name, () => {
        test.use({ viewport: device.viewport, hasTouch: device.hasTouch });
        test("find controls fit both tutors in every theme", async ({ page }, testInfo) => {
            const errors = [];
            page.on("pageerror", error => errors.push(error.message));
            await mockNotes(page);
            const press = locator => device.hasTouch ? locator.tap() : locator.click();
            for (const url of ["/#tutor", "/science"]) {
                await page.goto(url);
                await press(page.locator("#studyLibraryBtn"));
                await expect(rows(page)).toHaveCount(4);
                for (const theme of ["light", "dark", "neon"]) {
                    await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
                    await page.locator("#librarySearch").fill("equations");
                    await page.locator("#libraryFilterSubject").selectOption("math");
                    await expect(rows(page)).toHaveCount(2);
                    for (const control of await page.locator(".library-filters input, .library-filters select").all()) {
                        const bounds = await control.boundingBox();
                        expect(bounds.height).toBeGreaterThanOrEqual(44);
                        expect(bounds.x).toBeGreaterThanOrEqual(0);
                        expect(bounds.x + bounds.width).toBeLessThanOrEqual(device.viewport.width);
                    }
                    expect(await page.locator("#studyLibraryDialog").evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
                    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${url === "/science" ? "science" : "math"}-${theme}.png`) });
                    const add = page.getByRole("button", { name: "Add note", exact: true });
                    const addBounds = await add.boundingBox();
                    expect(addBounds.width).toBeGreaterThanOrEqual(44);
                    expect(addBounds.height).toBeGreaterThanOrEqual(44);
                    await press(add);
                    await expect(page.locator("#libraryAddNotesPanel")).toBeVisible();
                    await expect(add).toBeHidden();
                    await press(page.getByRole("button", { name: "Back to Study Library", exact: true }));
                    await expect(page.locator("#librarySearch")).toHaveValue("equations");
                    await expect(rows(page)).toHaveCount(2);
                    await press(page.locator("#libraryClearFilters"));
                    await expect(rows(page)).toHaveCount(4);
                }
                await press(page.locator("#closeStudyLibrary"));
            }
            expect(errors).toEqual([]);
        });
    });
}
