const { expect } = require("@playwright/test");

async function showAddForm(page) {
    const form = page.locator("#libraryAddNotesPanel");
    if (!await form.isVisible()) await page.getByRole("button", { name: "Add note", exact: true }).click();
    await expect(form).toBeVisible();
}

async function showLibraryList(page) {
    const list = page.locator("#libraryBrowse");
    if (!await list.isVisible()) await page.getByRole("button", { name: "Back to Study Library", exact: true }).click();
    await expect(list).toBeVisible();
}

module.exports = { showAddForm, showLibraryList };
