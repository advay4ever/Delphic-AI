const { test, expect } = require("@playwright/test");
const { showAddForm, showLibraryList } = require("./helpers/study-library");

const math = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable.";
const science = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process.";
const upload = (name = "imported_notes.txt", content = math) => ({ name, mimeType: "text/plain", buffer: Buffer.from(content) });

async function openNew(page, url) {
    await page.goto(url);
    await page.locator("#studyLibraryBtn").click();
    await showAddForm(page);
    await expect(page.locator("#studyLibraryNoteTitle")).toBeEnabled();
}

async function fillDraft(page, content = math) {
    await page.locator("#studyLibraryNoteTitle").fill("My unfinished note");
    await page.locator("#studyLibraryText").fill(content);
}

async function preventsLeaving(page) {
    return page.evaluate(() => {
        const event = new Event("beforeunload", { cancelable: true });
        window.dispatchEvent(event);
        return event.defaultPrevented;
    });
}

async function dropFile(page, name = "dropped_notes.txt") {
    await page.locator("#libraryDropzone").evaluate((zone, { name, content }) => {
        const transfer = new DataTransfer();
        transfer.items.add(new File([content], name, { type: "text/plain" }));
        zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, { name, content: math });
}

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: { configured: false, providers: [] } }));
    await page.route(/\/(?:science\/)?(?:ask|stream)$/, route => route.abort());
});

for (const url of ["/#tutor", "/science"]) {
    const content = url === "/science" ? science : math;

    test("upload needs consent before sending or replacing an unfinished note in " + url, async ({ page }) => {
        let previews = 0;
        await page.route("**/library/preview", route => {
            previews++;
            return route.fulfill({ json: { title: "imported_notes.txt", text: "Imported replacement. " + content } });
        });
        await openNew(page, url);
        await fillDraft(page, content);
        await page.locator("#studyLibrarySubject").selectOption("both");
        await page.locator("#studyLibraryEnabled").uncheck();
        await page.locator("#studyLibraryFile").setInputFiles(upload());
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        await expect(page.getByRole("button", { name: "Keep my note", exact: true })).toBeFocused();
        await expect(page.locator("#libraryUploadName")).toHaveText("imported_notes.txt");
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("My unfinished note");
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        expect(previews).toBe(0);
        await page.getByRole("button", { name: "Keep my note", exact: true }).click();
        await expect(page.locator("#libraryUploadConfirm")).toBeHidden();
        await expect(page.locator("#studyLibraryText")).toBeFocused();
        await expect(page.locator("#studyLibrarySubject")).toHaveValue("both");
        await expect(page.locator("#studyLibraryEnabled")).not.toBeChecked();
        await page.locator("#studyLibraryFile").setInputFiles([]);
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await page.locator("#studyLibraryFile").setInputFiles(upload());
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        expect(previews).toBe(0);
        await page.getByRole("button", { name: "Replace draft", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toContainText("Preview ready");
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("imported notes");
        await expect(page.locator("#studyLibraryText")).toHaveValue("Imported replacement. " + content);
        await expect(page.locator("#studyLibrarySubject")).toHaveValue("both");
        await expect(page.locator("#studyLibraryEnabled")).not.toBeChecked();
        expect(previews).toBe(1);
        expect((await (await page.request.get("/library/notes")).json()).notes).toEqual([]);
    });

    test("Escape keeps a dropped-file draft and file names stay plain text in " + url, async ({ page }) => {
        let previews = 0;
        await page.route("**/library/preview", route => { previews++; return route.abort(); });
        await openNew(page, url);
        await fillDraft(page, content);
        const name = "<img src=x onerror=alert(1)>.txt";
        await dropFile(page, name);
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        await expect(page.locator("#libraryUploadName")).toHaveText(name);
        await expect(page.locator("#libraryUploadConfirm img")).toHaveCount(0);
        await page.keyboard.press("Escape");
        await expect(page.locator("#libraryUploadConfirm")).toBeHidden();
        await expect(page.locator("#studyLibraryDialog")).toBeVisible();
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await expect(page.locator("#studyLibraryText")).toBeFocused();
        expect(previews).toBe(0);
        await dropFile(page);
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        await showLibraryList(page);
        await page.keyboard.press("Escape");
        await expect(page.locator("#studyLibraryDialog")).toBeHidden();
        await page.locator("#studyLibraryBtn").click();
        await showAddForm(page);
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        await page.getByRole("button", { name: "Keep my note", exact: true }).click();
    });

    test("failed or malformed previews keep the original draft and allow retry in " + url, async ({ page }) => {
        let previews = 0;
        await page.route("**/library/preview", route => {
            previews++;
            if (previews === 1) return route.fulfill({ status: 400, json: { error: "Unreadable document." } });
            if (previews === 2) return route.fulfill({ json: null });
            if (previews === 3) return route.fulfill({ json: { title: "must-not-overwrite.txt" } });
            return route.fulfill({ json: { title: "imported_notes.txt", text: "Replacement. " + content } });
        });
        await openNew(page, url);
        await fillDraft(page, content);
        await page.locator("#studyLibraryFile").setInputFiles({ name: "too-large.txt", mimeType: "text/plain", buffer: Buffer.alloc(4 * 1024 * 1024 + 1) });
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Choose a document no larger than 4 MiB.");
        await expect(page.locator("#libraryUploadConfirm")).toBeHidden();
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        expect(previews).toBe(0);
        for (const message of ["Unreadable document.",
            "That document preview could not be read. Your note has not changed.",
            "That document preview could not be read. Your note has not changed."]) {
            await page.locator("#studyLibraryFile").setInputFiles(upload());
            await page.getByRole("button", { name: "Replace draft", exact: true }).click();
            await expect(page.locator("#studyLibraryStatus")).toHaveText(message);
            await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("My unfinished note");
            await expect(page.locator("#studyLibraryText")).toHaveValue(content);
            await expect(page.locator("#studyLibraryText")).toBeEnabled();
            expect(await preventsLeaving(page)).toBe(true);
        }
        await page.locator("#studyLibraryFile").setInputFiles(upload());
        await page.getByRole("button", { name: "Replace draft", exact: true }).click();
        await expect(page.locator("#studyLibraryText")).toHaveValue("Replacement. " + content);
        expect(previews).toBe(4);
    });

    test("empty imports skip confirmation and successful saving clears the leave warning in " + url, async ({ page }) => {
        await page.route("**/library/preview", route => route.fulfill({ json: { title: "imported_notes.txt", text: content } }));
        await openNew(page, url);
        expect(await preventsLeaving(page)).toBe(false);
        await page.locator("#studyLibraryEnabled").uncheck();
        expect(await preventsLeaving(page)).toBe(false);
        await page.locator("#studyLibraryFile").setInputFiles(upload("imported_notes.txt", content));
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await expect(page.locator("#libraryUploadConfirm")).toBeHidden();
        expect(await preventsLeaving(page)).toBe(true);
        await page.locator("#studyLibraryFile").setInputFiles(upload());
        await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
        await page.getByRole("button", { name: "Save note", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
        await expect(page.locator("#libraryUploadConfirm")).toBeHidden();
        expect(await preventsLeaving(page)).toBe(false);
        const notes = (await (await page.request.get("/library/notes")).json()).notes;
        expect(notes).toHaveLength(1);
        expect(notes[0].text).toBe(content);
        expect(notes[0].enabled).toBe(0);
    });

    test("refresh and cross-tutor navigation warn even when a new draft is hidden in " + url, async ({ page }) => {
        await openNew(page, url);
        await page.locator("#studyLibraryNoteTitle").fill("Only a partial title");
        expect(await preventsLeaving(page)).toBe(true);
        let refreshType;
        page.once("dialog", async dialog => { refreshType = dialog.type(); await dialog.dismiss(); });
        await page.evaluate(() => window.location.reload());
        await expect.poll(() => refreshType).toBe("beforeunload");
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("Only a partial title");
        await page.locator("#studyLibraryNoteTitle").fill("");
        await page.locator("#studyLibraryText").fill(content);
        await showLibraryList(page);
        expect(await preventsLeaving(page)).toBe(true);
        const original = page.url();
        let navigationType;
        page.once("dialog", async dialog => { navigationType = dialog.type(); await dialog.dismiss(); });
        await page.evaluate(target => { window.location.href = target; }, url === "/science" ? "/#tutor" : "/science");
        await expect.poll(() => navigationType).toBe("beforeunload");
        expect(page.url()).toBe(original);
        await showAddForm(page);
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await page.locator("#studyLibraryText").fill("   \n");
        expect(await preventsLeaving(page)).toBe(false);
        await page.locator("#studyLibraryNoteTitle").fill("Explicitly discarded draft");
        let acceptedType;
        page.once("dialog", async dialog => { acceptedType = dialog.type(); await dialog.accept(); });
        await page.reload();
        expect(acceptedType).toBe("beforeunload");
        await page.locator("#studyLibraryBtn").click();
        await showAddForm(page);
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("");
        expect(await preventsLeaving(page)).toBe(false);
    });

    test("failed saving retains draft protection in " + url, async ({ page }) => {
        await page.route("**/library/notes", route => route.request().method() === "POST"
            ? route.fulfill({ status: 503, json: { error: "Try saving again." } }) : route.continue());
        await openNew(page, url);
        await fillDraft(page, content);
        await page.getByRole("button", { name: "Save note", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Try saving again.");
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("My unfinished note");
        expect(await preventsLeaving(page)).toBe(true);
        await page.locator("#closeStudyLibrary").click();
        expect(await preventsLeaving(page)).toBe(true);
        await page.locator("#studyLibraryBtn").click();
        await showAddForm(page);
        await expect(page.locator("#studyLibraryText")).toHaveValue(content);
    });

    test("saving an existing note does not clear a separate new draft in " + url, async ({ page }) => {
        await openNew(page, url);
        await page.request.post("/library/notes", { data: { title: "Stored note", text: content, subject: url === "/science" ? "science" : "math" } });
        await fillDraft(page, content);
        await showLibraryList(page);
        await page.locator("#closeStudyLibrary").click();
        await page.locator("#studyLibraryBtn").click();
        await page.getByRole("button", { name: "Actions for Stored note", exact: true }).click();
        await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
        await expect(page.locator("#libraryEditTitle")).toBeEnabled();
        await page.locator("#libraryEditTitle").fill("Updated stored note");
        await page.getByRole("button", { name: "Save changes", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note updated.");
        expect(await preventsLeaving(page)).toBe(true);
        await showAddForm(page);
        await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("My unfinished note");
        await page.locator("#studyLibraryNoteTitle").fill("");
        await page.locator("#studyLibraryText").fill("");
        expect(await preventsLeaving(page)).toBe(false);
    });

    test("replacement choices fit short and narrow screens in every theme in " + url, async ({ page }, testInfo) => {
        await openNew(page, url);
        await fillDraft(page, content);
        await page.locator("#studyLibraryFile").setInputFiles(upload("long_filename_".repeat(12) + ".txt"));
        for (const viewport of [{ width: 320, height: 600 }, { width: 820, height: 400 }, { width: 1280, height: 900 }]) {
            await page.setViewportSize(viewport);
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
                const keep = page.getByRole("button", { name: "Keep my note", exact: true });
                await keep.focus();
                await expect.poll(() => page.locator("#libraryUploadConfirm .library-edit-actions").evaluate(element => {
                    const bounds = element.getBoundingClientRect();
                    return bounds.bottom <= innerHeight;
                })).toBe(true);
                const header = await page.locator(".study-library-header").boundingBox();
                for (const control of await page.locator("#libraryUploadConfirm button").all()) {
                    const bounds = await control.boundingBox();
                    expect(bounds.height).toBeGreaterThanOrEqual(44);
                    expect(bounds.x).toBeGreaterThanOrEqual(0);
                    expect(bounds.x + bounds.width).toBeLessThanOrEqual(viewport.width);
                    expect(bounds.y).toBeGreaterThanOrEqual(header.y + header.height);
                    expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height);
                }
                expect(await page.locator("#studyLibraryDialog").evaluate(element => element.scrollWidth <= element.clientWidth + 1)).toBe(true);
                if (theme === "dark") await page.screenshot({ path: testInfo.outputPath(`replace-${viewport.width}.png`) });
            }
        }
    });
}
