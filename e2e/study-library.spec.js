const { test, expect } = require("@playwright/test");
const { showAddForm, showLibraryList } = require("./helpers/study-library");

const note = "Linear equations keep equality balanced. Subtract the same number from both sides of an equation to solve for a variable.";

for (const url of ["/#tutor", "/science"]) {
    test("save, select, preview and delete reusable notes in " + url, async ({ page }) => {
        await page.goto(url);
        await page.locator("#studyLibraryBtn").click();
        await expect(page.locator("#studyLibraryDialog")).toBeVisible();
        await expect(page.locator("#studyLibraryFile")).toBeEnabled();
        await showAddForm(page);
        await page.locator("#studyLibraryFile").setInputFiles({
            name: "class-notes.txt", mimeType: "text/plain", buffer: Buffer.from(note),
        });
        await expect(page.locator("#studyLibraryText")).toHaveValue(note);
        await expect(page.locator("#studyLibraryStatus")).toContainText("Preview ready");
        await page.locator("#studyLibrarySubject").selectOption("math");
        await page.locator("#studyLibraryNoteTitle").fill("<img src=x onerror=alert(1)>");
        await page.getByRole("button", { name: "Save note", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
        const saved = page.locator("#studyLibraryList li");
        await expect(saved).toHaveCount(1);
        await expect(saved.locator("strong")).toHaveText("<img src=x onerror=alert(1)>");
        await expect(saved.locator("img")).toHaveCount(0);
        await saved.locator("input[type=checkbox]").uncheck();
        await expect(page.locator("#studyLibraryStatus")).toContainText("disabled");
        await page.keyboard.press("Escape");
        await expect(page.locator("#studyLibraryDialog")).toBeHidden();
        await expect(page.locator("#studyLibraryBtn")).toBeFocused();
        await page.reload();
        await page.locator("#studyLibraryBtn").click();
        await expect(page.locator("#studyLibraryList input[type=checkbox]")).not.toBeChecked();
        await page.locator("#studyLibraryDialog").getByRole("button", { name: "Actions for" }).click();
        await page.getByRole("menuitem", { name: "Preview", exact: true }).click();
        await expect(page.locator("#studyLibraryList .library-note-preview p")).toHaveText(note);
        await page.locator("#studyLibraryDialog").getByRole("button", { name: "Actions for" }).click();
        await page.getByRole("menuitem", { name: "Delete", exact: true }).click();
        await page.getByRole("menuitem", { name: "Confirm delete", exact: true }).click();
        await expect(page.locator("#studyLibraryList")).toHaveText("No saved notes.");
    });
}

test("rejected subject keeps the draft and different browsers cannot see notes", async ({ browser, page }) => {
    await page.goto("/#tutor");
    await page.locator("#studyLibraryBtn").click();
    await showAddForm(page);
    await page.locator("#studyLibraryNoteTitle").fill("Notes");
    await page.locator("#studyLibraryText").fill(note);
    await page.locator("#studyLibrarySubject").selectOption("science");
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toContainText("This looks like Math");
    await expect(page.locator("#studyLibraryText")).toHaveValue(note);
    await expect(page.locator("#studyLibrarySubject")).toHaveValue("science");
    await page.getByRole("button", { name: "Use Math", exact: true }).click();
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note saved.");
    const context = await browser.newContext();
    try {
        const another = await context.newPage();
        await another.goto(new URL("/#tutor", page.url()).href);
        await another.locator("#studyLibraryBtn").click();
        await expect(another.locator("#studyLibraryList")).toHaveText("No saved notes.");
    } finally { await context.close(); }
});

test("saved references render safely and are included in HTML transcripts", async ({ page }) => {
    const sources = [{ title: "<script>bad</script>", subject: "math", excerpt: note + " <img src=x>", score: .5 }];
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "reference-chat", tokens_used: 0, images: [],
        messages: [{ id: 1, role: "assistant", content: "Use equality.", sources }],
    } }));
    await page.goto("/#tutor");
    await page.locator(".study-reference summary").click();
    await expect(page.locator(".study-reference strong")).toHaveText("<script>bad</script>");
    await expect(page.locator(".study-reference blockquote")).toContainText(note);
    await expect(page.locator(".study-reference script, .study-reference img")).toHaveCount(0);
    const html = await page.evaluate(sources => buildTranscriptHtml([
        { role: "assistant", content: "Use equality.", sources },
    ]), sources);
    expect(html).toContain("Matching notes");
    expect(html).toContain("&lt;script&gt;bad&lt;/script&gt;");
    expect(html).not.toContain("<img src=x>");
});

test("streamed answers show library reference metadata", async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "openai", provider_label: "OpenAI", model: "gpt-4.1", providers: [],
    } }));
    await page.route("**/stream", route => route.fulfill({
        contentType: "text/event-stream",
        body: "data: Keep both sides balanced.\n\nevent: complete\ndata: " + JSON.stringify({
            tokens_used: 1, finish_reason: "complete", message_id: 1, session_id: "test",
            sources: [{ title: "Equality", subject: "math", excerpt: note }],
        }) + "\n\n",
    }));
    await page.goto("/#tutor");
    await page.locator("#userInput").fill("Explain equality");
    await page.locator("#sendBtn").click();
    await expect(page.locator(".study-reference summary")).toHaveText("Matching notes (1)");
    await page.locator(".study-reference summary").click();
    await expect(page.locator(".study-reference blockquote")).toHaveText(note);
});

test("library dialog fits phones and desktops in every theme", async ({ page }, testInfo) => {
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    for (const width of [390, 1280]) {
        await page.setViewportSize({ width, height: 844 });
        await page.goto("/#tutor");
        if (width === 390) await page.locator("#menuBtn").click();
        await page.locator("#studyLibraryBtn").click();
        await expect(page.locator("#studyLibraryList")).toHaveText("No saved notes.");
        await expect(page.locator("#studyLibraryFile")).toBeEnabled();
        await showAddForm(page);
        for (const theme of ["light", "dark", "neon"]) {
            await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
            const box = await page.locator("#studyLibraryDialog").boundingBox();
            expect(box.x).toBeGreaterThanOrEqual(0);
            expect(box.x + box.width).toBeLessThanOrEqual(width);
            expect(box.y + box.height).toBeLessThanOrEqual(844);
            expect(await page.locator("#studyLibraryDialog").evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
            await page.screenshot({ path: testInfo.outputPath("library-" + width + "-" + theme + ".png") });
        }
        await page.keyboard.press("Escape");
    }
    expect(errors).toEqual([]);
});

test("plus, back, upload, rename and menu keyboard focus work without losing drafts", async ({ page }) => {
    await page.goto("/#tutor");
    await expect(page.locator("#libraryComposerStatus")).toContainText("Add study notes");
    await expect(page.locator("#libraryComposerStatus")).toHaveAttribute("aria-label", /0 Math notes enabled/);
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#libraryAddNotesPanel")).toBeVisible();
    await showLibraryList(page);
    await expect(page.locator("#libraryBrowse")).toBeVisible();
    await expect(page.locator("#studyLibraryDialog").getByRole("tab")).toHaveCount(0);
    await page.getByRole("button", { name: "Add note", exact: true }).focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#libraryUploadBtn")).toBeFocused();
    const chooserPromise = page.waitForEvent("filechooser");
    await page.locator("#libraryUploadBtn").click();
    const chooser = await chooserPromise;
    await chooser.setFiles({ name: "linear-equations.txt", mimeType: "text/plain", buffer: Buffer.from(note) });
    await expect(page.locator("#studyLibraryText")).toHaveValue(note);
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("linear equations");
    await showLibraryList(page);
    await showAddForm(page);
    await expect(page.locator("#studyLibraryText")).toHaveValue(note);
    await page.getByRole("button", { name: "Save note", exact: true }).click();
    await expect(page.locator("#libraryComposerLabel")).toHaveText("1 Math note enabled");
    const trigger = page.getByRole("button", { name: "Actions for linear equations", exact: true });
    await trigger.click();
    await expect(page.getByRole("menuitem", { name: "Preview", exact: true })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(trigger).toBeFocused();
    await expect(page.locator("#studyLibraryDialog")).toBeVisible();
    await trigger.click();
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await page.locator(".library-rename-form input").fill("Balance notes");
    await page.getByRole("button", { name: "Save title" }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note renamed.");
    await expect(page.locator("#studyLibraryList strong")).toHaveText("Balance notes");
    await page.keyboard.press("Escape");
    await expect(page.locator("#libraryComposerStatus")).toBeFocused();
    await page.reload();
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#studyLibraryList strong")).toHaveText("Balance notes");
    await page.locator("#studyLibraryList input[type=checkbox]").uncheck();
    await expect(page.locator("#libraryComposerStatus")).toContainText("Add study notes");
    await expect(page.locator("#libraryComposerStatus")).toHaveAttribute("aria-label", /0 Math notes enabled/);
});

test("dropped files preview and invalid drops preserve the draft", async ({ page }) => {
    await page.goto("/#tutor");
    await page.locator("#studyLibraryBtn").click();
    await showAddForm(page);
    await page.locator("#studyLibraryNoteTitle").fill("Draft title");
    await page.locator("#studyLibraryText").fill(note);
    await page.locator("#libraryDropzone").evaluate((zone, content) => {
        const transfer = new DataTransfer();
        transfer.items.add(new File([content], "one.txt", { type: "text/plain" }));
        transfer.items.add(new File([content], "two.txt", { type: "text/plain" }));
        zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, note);
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Upload one document at a time.");
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("Draft title");
    await page.locator("#libraryDropzone").evaluate((zone, content) => {
        const transfer = new DataTransfer();
        transfer.items.add(new File([content], "my_notes.txt", { type: "text/plain" }));
        zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
    }, note);
    await expect(page.locator("#libraryUploadConfirm")).toBeVisible();
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("Draft title");
    await page.getByRole("button", { name: "Replace draft", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toContainText("Preview ready");
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("my notes");
    await page.route("**/library/preview", route => route.fulfill({ status: 400, json: { error: "Unreadable document." } }));
    await page.locator("#studyLibraryFile").setInputFiles({ name: "bad.txt", mimeType: "text/plain", buffer: Buffer.from("bad") });
    await page.getByRole("button", { name: "Replace draft", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Unreadable document.");
    await expect(page.locator("#studyLibraryText")).toHaveValue(note);
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("my notes");
});

test("note menus fit small screens and failed changes do not erase notes", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "A very long title about equations and keeping both sides balanced", subject: "math", text: note, enabled: true } });
    await page.locator("#libraryComposerStatus").click();
    await showLibraryList(page);
    await expect(page.locator("#studyLibraryList strong")).toBeVisible();
    for (const theme of ["light", "dark", "neon"]) {
        await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
        await page.locator("#studyLibraryDialog").getByRole("button", { name: "Actions for" }).click();
        const menu = page.getByRole("menu", { name: "Actions for" });
        const box = await menu.boundingBox();
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(390);
        expect(box.y + box.height).toBeLessThanOrEqual(844);
        await page.screenshot({ path: testInfo.outputPath("library-menu-" + theme + ".png") });
        await page.keyboard.press("Escape");
    }
    await page.route("**/library/notes/*", route => route.fulfill({ status: 400, json: { error: "Try again." } }));
    await page.locator("#studyLibraryList input[type=checkbox]").uncheck();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Try again.");
    await expect(page.locator("#studyLibraryList input[type=checkbox]")).toBeChecked();
    await page.locator("#studyLibraryDialog").getByRole("button", { name: "Actions for" }).click();
    await page.getByRole("menuitem", { name: "Rename", exact: true }).click();
    await page.locator(".library-rename-form input").fill("My revised draft");
    await page.getByRole("button", { name: "Save title" }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Try again.");
    await expect(page.locator(".library-rename-form input")).toHaveValue("My revised draft");
});

test("failed status is not presented as zero notes", async ({ page }) => {
    await page.route("**/library/status?*", route => route.fulfill({ status: 503, json: { error: "Unavailable" } }));
    await page.goto("/#tutor");
    await expect(page.locator("#libraryComposerLabel")).toHaveText("Notes unavailable");
});

for (const operation of ["preview", "save"]) {
    test("reopening keeps a pending " + operation + " from overwriting a newer draft", async ({ page }) => {
        let release, started;
        const pending = new Promise(resolve => { release = resolve; });
        const requested = new Promise(resolve => { started = resolve; });
        const path = operation === "preview" ? "**/library/preview" : "**/library/notes";
        let writes = 0;
        await page.route(path, async route => {
            if (route.request().method() !== "POST") return route.continue();
            writes += 1;
            started();
            await pending;
            await route.fulfill({ status: operation === "save" ? 201 : 200,
                json: operation === "save" ? { id: "saved-test-note" } : { title: "old-upload.txt", text: note } });
        });
        try {
            await page.goto("/#tutor");
            await page.locator("#studyLibraryBtn").click();
            await showAddForm(page);
            if (operation === "preview") {
                await page.locator("#studyLibraryFile").setInputFiles({ name: "old-upload.txt", mimeType: "text/plain", buffer: Buffer.from(note) });
            } else {
                await page.locator("#studyLibraryNoteTitle").fill("Original note");
                await page.locator("#studyLibraryText").fill(note);
                await page.getByRole("button", { name: "Save note", exact: true }).click();
            }
            await requested;
            await page.locator("#closeStudyLibrary").click();
            await page.locator("#studyLibraryBtn").click();
            await showAddForm(page);
            await expect(page.locator("#studyLibraryNoteTitle")).toBeDisabled();
            await expect(page.locator("#studyLibraryText")).toBeDisabled();
            await expect(page.getByRole("button", { name: "Save note", exact: true })).toBeDisabled();
            release();
            await expect(page.locator("#studyLibraryStatus")).toContainText(operation === "save" ? "Note saved." : "Preview ready");
            await showAddForm(page);
            await page.locator("#studyLibraryNoteTitle").fill("New draft");
            await page.locator("#studyLibraryText").fill("New draft: " + note);
            await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("New draft");
            await expect(page.locator("#studyLibraryText")).toHaveValue("New draft: " + note);
            expect(writes).toBe(1);
        } finally { release(); }
    });
}

async function openNoteEditor(page, title = "Class notes") {
    await page.locator("#libraryComposerStatus").click();
    await showLibraryList(page);
    await page.getByRole("button", { name: "Actions for " + title, exact: true }).click();
    await page.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await expect(page.locator("#libraryEditTitle")).toHaveValue(title);
    await expect(page.locator("#libraryEditTitle")).toBeEnabled();
}

for (const url of ["/#tutor", "/science"]) {
    test("edit saved note title, subject and text in " + url, async ({ page }) => {
        await page.goto(url);
        await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note, enabled: false } });
        await openNoteEditor(page);
        const science = "Photosynthesis allows plants to use sunlight energy and carbon dioxide to make sugars. Chloroplasts in plant cells perform this process.";
        await page.locator("#libraryEditTitle").fill("Plant notes <script>");
        await page.locator("#libraryEditSubject").selectOption("science");
        await page.locator("#libraryEditText").fill(science);
        await page.getByRole("button", { name: "Save changes", exact: true }).click();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note updated.");
        await expect(page.locator("#libraryEditForm")).toBeHidden();
        await expect(page.locator("#studyLibraryList strong")).toHaveText("Plant notes <script>");
        await expect(page.locator("#studyLibraryList .library-note-subject")).toHaveText("Science");
        await expect(page.locator("#studyLibraryList input[type=checkbox]")).not.toBeChecked();
        await expect(page.getByRole("button", { name: "Actions for Plant notes <script>", exact: true })).toBeFocused();
        await page.keyboard.press("Escape");
        await page.reload();
        await openNoteEditor(page, "Plant notes <script>");
        await expect(page.locator("#libraryEditText")).toHaveValue(science);
        await expect(page.locator("#libraryEditSubject")).toHaveValue("science");
        await page.getByRole("button", { name: "Cancel", exact: true }).click();
        await expect(page.locator("#libraryEditForm")).toBeHidden();
    });
}

test("add and edit drafts survive back navigation, closing, subject errors and failed saves", async ({ page }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note } });
    await page.locator("#studyLibraryBtn").click();
    await showAddForm(page);
    await page.locator("#studyLibraryNoteTitle").fill("Separate add draft");
    await page.locator("#closeStudyLibrary").click();
    await openNoteEditor(page);
    const draft = note + " Extra example: x + 5 = 12, so x = 7.";
    await page.locator("#libraryEditText").fill(draft);
    await page.getByRole("button", { name: "Back to Study Library", exact: true }).click();
    await expect(page.locator("#libraryEditDiscard")).toBeVisible();
    await page.getByRole("button", { name: "Keep editing", exact: true }).click();
    await page.locator("#closeStudyLibrary").click();
    await page.locator("#libraryComposerStatus").click();
    await expect(page.locator("#libraryEditText")).toHaveValue(draft);
    await page.locator("#libraryEditSubject").selectOption("science");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("#libraryEditError")).toContainText("This looks like Math");
    await expect(page.locator("#libraryEditSubject")).toBeFocused();
    await expect(page.locator("#libraryEditSubject")).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#libraryEditText")).toHaveValue(draft);
    await page.locator("#libraryEditSubject").selectOption("math");
    await page.route("**/library/notes/*", route => route.fulfill({ status: 503, json: { error: "Try again later." } }));
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("#libraryEditError")).toHaveText("Try again later.");
    await expect(page.locator("#libraryEditText")).toHaveValue(draft);
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.locator("#libraryEditDiscard")).toBeVisible();
    await page.getByRole("button", { name: "Keep editing", exact: true }).click();
    await expect(page.locator("#libraryEditText")).toHaveValue(draft);
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Discard changes", exact: true }).click();
    await expect(page.locator("#studyLibraryList strong")).toHaveText("Class notes");
    await showAddForm(page);
    await expect(page.locator("#studyLibraryNoteTitle")).toHaveValue("Separate add draft");
    const saved = (await (await page.request.get("/library/notes")).json()).notes[0];
    expect(saved.text).toBe(note);
    expect(saved.revision).toBe(1);
});

test("two editors cannot silently overwrite each other and reload needs consent", async ({ page, context }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note } });
    await openNoteEditor(page);
    const other = await context.newPage();
    await other.goto("/science");
    await openNoteEditor(other);
    await page.locator("#libraryEditTitle").fill("Latest saved title");
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("#studyLibraryStatus")).toHaveText("Note updated.");
    await other.locator("#libraryEditTitle").fill("My unsaved title");
    await other.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(other.locator("#libraryEditError")).toContainText("changed in another tab");
    await expect(other.locator("#libraryEditTitle")).toHaveValue("My unsaved title");
    await other.getByRole("button", { name: "Load latest saved note", exact: true }).click();
    await expect(other.locator("#libraryEditTitle")).toHaveValue("My unsaved title");
    await other.getByRole("button", { name: "Keep editing", exact: true }).click();
    await other.getByRole("button", { name: "Load latest saved note", exact: true }).click();
    await other.getByRole("button", { name: "Discard changes", exact: true }).click();
    await expect(other.locator("#libraryEditTitle")).toHaveValue("Latest saved title");
    await other.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(other.locator("#studyLibraryList strong")).toHaveText("Latest saved title");
    await other.getByRole("button", { name: "Actions for Latest saved title", exact: true }).click();
    await other.getByRole("menuitem", { name: "Edit note", exact: true }).click();
    await expect(other.locator("#libraryEditTitle")).toBeEnabled();
    await other.locator("#libraryEditTitle").fill("Reviewed title");
    await other.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(other.locator("#studyLibraryStatus")).toHaveText("Note updated.");
    const saved = (await (await page.request.get("/library/notes")).json()).notes[0];
    expect(saved.title).toBe("Reviewed title");
    expect(saved.revision).toBe(3);
});

test("reopening during an edit save keeps fields locked and preserves selection", async ({ page }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note } });
    await openNoteEditor(page);
    let release, started;
    const pending = new Promise(resolve => { release = resolve; });
    const requested = new Promise(resolve => { started = resolve; });
    await page.route("**/library/notes/*", async route => {
        started(); await pending; await route.continue();
    });
    try {
        await page.locator("#libraryEditTitle").fill("Updated title");
        await page.getByRole("button", { name: "Save changes", exact: true }).click();
        await requested;
        await page.locator("#closeStudyLibrary").click();
        await page.locator("#libraryComposerStatus").click();
        await expect(page.locator("#libraryEditTitle")).toBeDisabled();
        await expect(page.getByRole("button", { name: "Cancel", exact: true })).toBeDisabled();
        release();
        await expect(page.locator("#studyLibraryStatus")).toHaveText("Note updated.");
        await expect(page.locator("#studyLibraryList input[type=checkbox]")).toBeChecked();
    } finally { release(); }
});

test("long note editor fits phone and desktop themes", async ({ page }, testInfo) => {
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note.repeat(70) } });
    await openNoteEditor(page);
    for (const width of [390, 1280]) {
        await page.setViewportSize({ width, height: 844 });
        for (const theme of ["light", "dark", "neon"]) {
            await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
            const dialog = page.locator("#studyLibraryDialog");
            expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
            const box = await dialog.boundingBox();
            expect(box.x).toBeGreaterThanOrEqual(0);
            expect(box.x + box.width).toBeLessThanOrEqual(width);
            await page.getByRole("button", { name: "Save changes", exact: true }).scrollIntoViewIfNeeded();
            await expect(page.getByRole("button", { name: "Save changes", exact: true })).toBeInViewport();
            await page.screenshot({ path: testInfo.outputPath("library-edit-" + width + "-" + theme + ".png") });
        }
    }
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    expect(errors).toEqual([]);
});

test("a deleted note does not erase an open edit draft", async ({ page }) => {
    await page.goto("/#tutor");
    const saved = await (await page.request.post("/library/notes", {
        data: { title: "Class notes", subject: "math", text: note },
    })).json();
    await openNoteEditor(page);
    await page.locator("#libraryEditTitle").fill("My remaining draft");
    await page.request.delete("/library/notes/" + saved.id);
    await page.getByRole("button", { name: "Save changes", exact: true }).click();
    await expect(page.locator("#libraryEditError")).toContainText("not found");
    await expect(page.locator("#libraryEditTitle")).toHaveValue("My remaining draft");
    await expect(page.locator("#libraryEditText")).toHaveValue(note);
    expect((await (await page.request.get("/library/notes")).json()).notes).toEqual([]);
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Discard changes", exact: true }).click();
});

test("refresh warns before losing an unsaved edit but clean edits need no warning", async ({ page }) => {
    await page.goto("/#tutor");
    await page.request.post("/library/notes", { data: { title: "Class notes", subject: "math", text: note } });
    await openNoteEditor(page);
    const prevented = () => page.evaluate(() => {
        const event = new Event("beforeunload", { cancelable: true });
        window.dispatchEvent(event); return event.defaultPrevented;
    });
    expect(await prevented()).toBe(false);
    await page.locator("#libraryEditTitle").fill("Unsaved title");
    let type;
    page.once("dialog", async dialog => { type = dialog.type(); await dialog.dismiss(); });
    await page.evaluate(() => window.location.reload());
    await expect.poll(() => type).toBe("beforeunload");
    await expect(page.locator("#libraryEditTitle")).toHaveValue("Unsaved title");
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await page.getByRole("button", { name: "Discard changes", exact: true }).click();
    expect(await prevented()).toBe(false);
});
