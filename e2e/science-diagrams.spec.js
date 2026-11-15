const { expect, test } = require("@playwright/test");

const forceDiagram = {
    version: 1,
    type: "force_diagram",
    title: "Forces on a box",
    description: "A free-body diagram showing forces on a box.",
    objects: [
        { id: "box", kind: "box", x: 38, y: 37, width: 24, height: 20, label: "Box" },
        { id: "normal", kind: "arrow", x1: 50, y1: 37, x2: 50, y2: 9, label: "Normal force" },
        { id: "weight", kind: "arrow", x1: 50, y1: 57, x2: 50, y2: 85, label: "Weight" },
        { id: "applied", kind: "arrow", x1: 62, y1: 47, x2: 91, y2: 47, label: "Applied force" },
        { id: "friction", kind: "arrow", x1: 38, y1: 47, x2: 9, y2: 47, label: "Friction" },
    ],
};

const circuitDiagram = {
    version: 1,
    type: "circuit_diagram",
    title: "Simple closed circuit",
    description: "A battery and resistor connected by one complete wire loop.",
    objects: [
        { id: "wire-top-left", kind: "line", x1: 20, y1: 18, x2: 41, y2: 18 },
        { id: "resistor", kind: "resistor", x: 41, y: 13, width: 22, height: 10, label: "Resistor" },
        { id: "wire-top-right", kind: "line", x1: 63, y1: 18, x2: 84, y2: 18 },
        { id: "wire-right", kind: "line", x1: 84, y1: 18, x2: 84, y2: 74 },
        { id: "wire-bottom", kind: "line", x1: 84, y1: 74, x2: 20, y2: 74 },
        { id: "wire-left-top", kind: "line", x1: 20, y1: 18, x2: 20, y2: 42 },
        { id: "battery", kind: "battery", x: 14, y: 38, width: 12, height: 18, label: "Battery" },
        { id: "wire-left-bottom", kind: "line", x1: 20, y1: 51, x2: 20, y2: 74 },
        { id: "current", kind: "arrow", x1: 67, y1: 74, x2: 42, y2: 74, label: "Current" },
    ],
};

const waterCycleDiagram = {
    version: 1,
    type: "process_diagram",
    title: "The water cycle",
    description: "Water moves through evaporation, condensation, precipitation, and collection.",
    objects: [
        { id: "ocean", kind: "box", x: 8, y: 72, width: 27, height: 13, label: "Ocean" },
        { id: "vapor", kind: "ellipse", cx: 22, cy: 25, rx: 14, ry: 9, label: "Water vapor" },
        { id: "cloud", kind: "ellipse", cx: 69, cy: 24, rx: 17, ry: 10, label: "Clouds" },
        { id: "land", kind: "box", x: 65, y: 72, width: 27, height: 13, label: "Land" },
        { id: "evaporation", kind: "arrow", x1: 20, y1: 72, x2: 20, y2: 36, label: "Evaporation" },
        { id: "condensation", kind: "arrow", x1: 36, y1: 24, x2: 51, y2: 24, label: "Condensation" },
        { id: "precipitation", kind: "arrow", x1: 72, y1: 34, x2: 76, y2: 68, label: "Precipitation" },
        { id: "collection", kind: "arrow", x1: 65, y1: 79, x2: 39, y2: 79, label: "Collection" },
    ],
};

const plantCellDiagram = {
    version: 1,
    type: "labeled_structure",
    title: "Main parts of a plant cell",
    description: "A simplified plant cell with its main parts labeled.",
    objects: [
        { id: "cell-wall", kind: "box", x: 7, y: 12, width: 86, height: 76, label: "Cell wall" },
        { id: "cell-membrane", kind: "box", x: 11, y: 16, width: 78, height: 68, label: "Cell membrane" },
        { id: "vacuole", kind: "ellipse", cx: 56, cy: 52, rx: 20, ry: 22, label: "Central vacuole" },
        { id: "nucleus", kind: "circle", cx: 28, cy: 48, r: 8, label: "Nucleus" },
        { id: "chloroplast", kind: "ellipse", cx: 44, cy: 22, rx: 9, ry: 5, label: "Chloroplast" },
        { id: "wall-callout", kind: "line", x1: 87, y1: 12, x2: 92, y2: 8 },
        { id: "wall-label", kind: "label", x: 95, y: 7, text: "Cell wall", anchor: "end" },
        { id: "membrane-callout", kind: "line", x1: 85, y1: 84, x2: 92, y2: 92 },
        { id: "membrane-label", kind: "label", x: 95, y: 97, text: "Cell membrane", anchor: "end" },
        { id: "vacuole-label", kind: "label", x: 56, y: 53, text: "Central vacuole", anchor: "middle" },
        { id: "nucleus-label", kind: "label", x: 28, y: 49, text: "Nucleus", anchor: "middle" },
        { id: "chloroplast-label", kind: "label", x: 44, y: 23, text: "Chloroplast", anchor: "middle" },
        { id: "cytoplasm-label", kind: "label", x: 27, y: 72, text: "Cytoplasm", anchor: "middle" },
    ],
};

const allDiagrams = [forceDiagram, circuitDiagram, waterCycleDiagram, plantCellDiagram];

async function mockSciencePage(page, messages = []) {
    await page.route("**/science/history", route => route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ session_id: "science:test", tokens_used: 12, messages }),
    }));
    await page.route("**/ai-settings", route => route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ configured: true, provider: "groq", model: "test", providers: [] }),
    }));
    await page.goto("/science");
}

test("all saved science diagram families are readable, accessible, and safe", async ({ page }) => {
    const browserErrors = [];
    page.on("pageerror", error => browserErrors.push(error.message));
    await mockSciencePage(page, allDiagrams.map((diagram, index) => ({
        id: index + 5,
        role: "assistant",
        content: `Explanation for ${diagram.title}.\n\nCONFIDENCE: High`,
        finish_reason: "complete",
        continuation_count: 0,
        can_continue: false,
        diagram,
    })));

    const diagrams = page.locator(".science-diagram");
    await expect(diagrams).toHaveCount(4);
    for (const [index, spec] of allDiagrams.entries()) {
        const diagram = diagrams.nth(index);
        await expect(diagram).toBeVisible();
        await expect(diagram.getByRole("heading", { name: spec.title })).toBeVisible();
        await expect(diagram.locator("svg")).toHaveAttribute("aria-label", spec.description);
    }
    await expect(diagrams.nth(0).locator("text")).toContainText(["Box", "Normal force", "Weight"]);
    await expect(diagrams.nth(1)).toContainText("Battery");
    await expect(diagrams.nth(2)).toContainText("Precipitation");
    await expect(diagrams.nth(3)).toContainText("Central vacuole");
    await diagrams.nth(0).focus();
    await expect(diagrams.nth(0)).toBeFocused();
    expect(browserErrors).toEqual([]);
});

test("unsafe or malformed diagram data is not drawn", async ({ page }) => {
    const unsafeDiagram = structuredClone(forceDiagram);
    unsafeDiagram.objects[0].label = "<script>alert(1)</script>";
    await mockSciencePage(page, [{
        id: 8,
        role: "assistant",
        content: "The written explanation remains available.",
        finish_reason: "complete",
        diagram: unsafeDiagram,
    }]);

    await expect(page.locator(".message.assistant").getByText("written explanation")).toBeVisible();
    await expect(page.locator(".science-diagram")).toHaveCount(0);
    await expect(page.locator("script:not([src])")).toHaveCount(0);
});

test("science diagrams fit a phone and all three themes", async ({ browser }) => {
    const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
    });
    const page = await context.newPage();
    await mockSciencePage(page, [{
        id: 9,
        role: "assistant",
        content: "A force diagram.",
        finish_reason: "complete",
        diagram: forceDiagram,
    }]);

    for (const theme of ["light", "dark", "neon"]) {
        await page.locator("#aiSettingsBtn").click();
        await page.locator("#themeToggle").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.keyboard.press("Escape");
        await expect(page.locator(".science-diagram")).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    await context.close();
});

test("HTML transcripts include the checked local diagram", async ({ page }) => {
    await mockSciencePage(page);
    const transcript = await page.evaluate(diagram => window.buildTranscriptHtml([{
        role: "assistant",
        content: "The arrows show the forces.",
        diagram,
    }]), forceDiagram);

    expect(transcript).toContain("Forces on a box");
    expect(transcript).toContain("Normal force");
    expect(transcript).toContain("<svg");
    expect(transcript).not.toContain("science-diagrams.js");
});
