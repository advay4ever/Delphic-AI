const { test, expect } = require("@playwright/test");
const { showAddForm, showLibraryList } = require("./helpers/study-library");

const math = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable.";
const science = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process.";
const upload = text => ({ name: "class-notes.txt", mimeType: "text/plain", buffer: Buffer.from(text) });

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: false, provider: "groq", model: "openai/gpt-oss-120b", providers: [],
    } }));
    await page.route(/\/(?:science\/)?(?:ask|stream)$/, route => route.abort());
});

for (const [url, subject, text] of [["/#tutor", "math", math], ["/science", "science", science]]) {
    test("single library list and plus button save a note in " + subject, async ({ page }) => {
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        const dialog = page.locator("#studyLibraryDialog");
        await expect(dialog.getByRole("tablist")).toHaveCount(0);
        await expect(page.locator("#libraryBrowse")).toBeVisible();
        const add = dialog.getByRole("button", { name: "Add note", exact: true });
        await expect(add).toHaveCount(1);
        await expect(add).toHaveAttribute("title", "Add note");
        await expect(add).toBeEnabled();
        await add.focus();
        await page.keyboard.press("Enter");
        await expect(page.locator("#libraryUploadBtn")).toBeFocused();
        await page.locator("#studyLibraryNoteTitle").fill("My first note");
        await page.locator("#studyLibraryText").fill(text);
        await page.getByRole("button", { name: "Back to Study Library", exact: true }).click();
        await expect(page.locator("#studyLibraryList")).toHaveText("No saved notes.");
        await add.click();
        await expect(page.locator("#studyLibraryText")).toHaveValue(text);
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("My first note");
        await expect(page.locator("#studyLibrarySubject")).toHaveValue(subject);
        await page.getByRole("button", { name: "Save note", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
        await expect(page.locator("#libraryBrowse")).toBeVisible();
        await expect(page.locator("#studyLibraryList strong")).toHaveText("My first note");
        await expect(page.getByRole("button", { name: "Actions for My first note", exact: true })).toBeFocused();
        await expect(add).toBeVisible();
        await expect(page.getByRole("button", { name: "Back to Study Library", exact: true })).toBeHidden();
    });

    test("add notes from the composer without AI setup in " + subject, async ({ page }) => {
        await page.goto(url);
        const badge = page.locator("#libraryComposerStatus");
        await expect(badge).toContainText("Add study notes");
        await badge.click();
        await expect(page.locator("#libraryAddNotesPanel")).toBeVisible();
        await expect(page.locator("#libraryUploadBtn")).toBeFocused();
        await page.locator("#studyLibraryFile").setInputFiles(upload(text));
        await expect(page.locator("#studyLibraryText")).toHaveValue(text);
        await expect(page.locator("#studyLibrarySubject")).toHaveValue(subject);
        expect((await (await page.request.get("/library/notes")).json()).notes).toEqual([]);
        await expect(page.locator("#librarySavePrivacy")).toContainText("passwords, API keys, and private student information");
        await page.getByRole("button", { name: "Save note", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
        await expect(badge).toContainText("1 " + (subject === "math" ? "Math" : "Science") + " note enabled");
        await expect(page.locator("#libraryComposerIcon")).toBeHidden();
        await page.locator("#closeStudyLibrary").click();
        await expect(badge).toBeFocused();
        await badge.click();
        await expect(page.locator("#libraryBrowse")).toBeVisible();
        await expect(page.locator("#studyLibraryList strong")).toHaveText("class notes");
        await expect(page.locator("#aiSettingsModal")).toBeHidden();
    });
}

test("zero enabled notes does not hide disabled or other-subject saved notes", async ({ page }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Disabled algebra", subject: "math", text: math, enabled: false } });
    await page.request.post("/library/notes", { data: { title: "Plant notes", subject: "science", text: science } });
    await expect(page.locator("#libraryComposerStatus")).toContainText("Add study notes");
    await page.locator("#libraryComposerStatus").click();
    await showLibraryList(page);
    await expect(page.locator("#studyLibraryList li")).toHaveCount(2);
    await expect(page.getByRole("button", { name: "Add note", exact: true })).toBeVisible();
    const row = page.locator("#studyLibraryList li").filter({ hasText: "Disabled algebra" });
    await row.getByRole("checkbox").check();
    await expect(page.locator("#libraryComposerStatus")).toContainText("1 Math note enabled");
    await page.locator("#closeStudyLibrary").click();
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#libraryBrowse")).toBeVisible();
});

test("empty library has a direct add action and no AI-key requirement", async ({ page }) => {
    await page.goto("/#tutor");
    await page.locator("#studyLibraryBtn").click();
    await expect(page.locator("#studyLibraryList")).toHaveText("No saved notes.");
    await page.getByRole("button", { name: "Add note", exact: true }).click();
    await expect(page.locator("#libraryAddNotesPanel")).toBeVisible();
    await expect(page.locator("#libraryUploadBtn")).toBeFocused();
    await expect(page.locator("#aiSettingsModal")).toBeHidden();
});

test("plus menu saves reusable notes separately from attachments and preserves both drafts", async ({ page }) => {
    await page.goto("/#tutor");
    await page.locator("#userInput").fill("My unsent question");
    await page.locator("#attachmentFileInput").setInputFiles({ ...upload(math), name: "one-question.txt" });
    await page.locator("#attachmentBtn").click();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await expect(page.getByRole("menuitem", { name: "Save study notes", exact: true })).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#attachmentMenu")).toBeHidden();
    await expect(page.locator("#studyLibraryDialog")).toBeVisible();
    await expect(page.locator("#libraryAddNotesPanel")).toBeVisible();
    await expect(page.locator("#studyLibraryFile")).toBeEnabled();
    await page.locator("#studyLibraryFile").setInputFiles(upload(math));
    await expect(page.locator("#studyLibraryText")).toHaveValue(math);
    expect((await (await page.request.get("/library/notes")).json()).notes).toEqual([]);
    await page.keyboard.press("Escape");
    await expect(page.locator("#attachmentBtn")).toBeFocused();
    await expect(page.locator("#attachmentTray")).toContainText("one-question.txt");
    await expect(page.locator("#userInput")).toHaveValue("My unsent question");
    await page.locator("#attachmentBtn").click();
    await page.getByRole("menuitem", { name: "Save study notes", exact: true }).click();
    await expect(page.locator("#studyLibraryText")).toHaveValue(math);
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("class notes");
    await expect(page.locator("#aiSettingsModal")).toBeHidden();
});

test("unavailable note counts never pretend the library is empty", async ({ page }) => {
    await page.route("**/library/status?*", route => route.fulfill({ json: {} }));
    await page.goto("/#tutor");
    await expect(page.locator("#libraryComposerLabel")).toHaveText("Notes unavailable");
    await expect(page.locator("#libraryComposerIcon")).toBeHidden();
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#libraryBrowse")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add note", exact: true })).toBeVisible();
});

test("add shortcut preserves an unfinished edit when no notes are enabled", async ({ page }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Algebra", subject: "math", text: math, enabled: false } });
    await page.locator("#studyLibraryBtn").click();
    await page.getByRole("button", { name: "Actions for Algebra", exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await page.locator("#libraryEditText").fill(math + " My unfinished edit.");
    await page.locator("#closeStudyLibrary").click();
    await expect(page.locator("#libraryComposerStatus")).toContainText("Add study notes");
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#libraryEditForm")).toBeVisible();
    await expect(page.getByRole("button", { name: "Add note", exact: true })).toBeHidden();
    await expect(page.locator("#libraryEditText")).toHaveValue(math + " My unfinished edit.");
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Discard changes", exact: true }).click();
});

for (const device of [
    { name: "computer", viewport: { width: 1280, height: 900 }, hasTouch: false },
    { name: "iPad portrait simulation", viewport: { width: 820, height: 1180 }, hasTouch: true },
    { name: "iPad landscape simulation", viewport: { width: 1180, height: 820 }, hasTouch: true },
]) {
    test.describe(device.name, () => {
        test.use({ viewport: device.viewport, hasTouch: device.hasTouch });
        test("notes entry points and saving fit both tutors and all themes", async ({ page }, testInfo) => {
            const errors = [];
            page.on("pageerror", error => errors.push(error.message));
            const press = locator => device.hasTouch ? locator.tap() : locator.click();
            for (const url of ["/#tutor", "/science"]) {
                await page.goto(url);
                const badge = page.locator("#libraryComposerStatus");
                await expect(badge).toContainText("Add study notes");
                for (const theme of ["light", "dark", "neon"]) {
                    await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
                    const badgeBox = await badge.boundingBox();
                    expect(badgeBox.height).toBeGreaterThanOrEqual(44);
                    expect(badgeBox.x + badgeBox.width).toBeLessThanOrEqual(device.viewport.width);
                    expect(badgeBox.y + badgeBox.height).toBeLessThanOrEqual(device.viewport.height);
                    await press(badge);
                    const panel = page.locator("#studyLibraryDialog");
                    await expect(page.locator("#libraryUploadBtn")).toBeEnabled();
                    const bounds = await panel.boundingBox();
                    expect(bounds.x).toBeGreaterThanOrEqual(0);
                    expect(bounds.x + bounds.width).toBeLessThanOrEqual(device.viewport.width);
                    expect(bounds.y + bounds.height).toBeLessThanOrEqual(device.viewport.height);
                    expect(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
                    await page.getByRole("button", { name: "Save note", exact: true }).scrollIntoViewIfNeeded();
                    await expect(page.locator("#librarySavePrivacy")).toBeInViewport();
                    await expect(page.getByRole("button", { name: "Save note", exact: true })).toBeInViewport();
                    await page.screenshot({ animations: "disabled", path: testInfo.outputPath(`${url === "/science" ? "science" : "math"}-${theme}.png`) });
                    await press(page.locator("#closeStudyLibrary"));
                    await expect(badge).toBeFocused();
                }
            }
            expect(errors).toEqual([]);
        });
    });
}
