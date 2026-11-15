const { expect, test } = require("@playwright/test");

async function openMathTutor(page) {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
}

async function addSurfaceGraph(page, message) {
    await page.evaluate(async graphMessage => {
        const response = await fetch("/plot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: graphMessage }),
        });
        const graphSpec = await response.json();
        if (!response.ok) throw new Error(graphSpec.error || "Could not create graph data.");
        removeTutorWelcome();

        const messageElement = document.createElement("div");
        messageElement.className = "message assistant";
        const content = document.createElement("div");
        content.className = "message-content graph-card";
        const container = document.createElement("div");
        container.className = "local-graph-container";
        container.graphSpec = graphSpec;
        content.appendChild(container);
        messageElement.appendChild(content);
        document.querySelector("#chatMessages").appendChild(messageElement);
        window.DelphicGraphing.renderGraph(
            container,
            graphSpec,
            document.documentElement.getAttribute("data-theme") || "dark"
        );
    }, message);

    const graph = page.locator(".local-graph-container").last();
    await expect(graph.locator("canvas")).toBeVisible();
    // This fixture bypasses normal message insertion, including its bottom scroll.
    await page.locator("#chatMessages").evaluate(element => {
        element.scrollTo({ top: element.scrollHeight, behavior: "instant" });
    });
    return graph;
}

async function hoverAVisibleSurfacePoint(page, graph) {
    const canvas = graph.locator("canvas");
    const box = await canvas.boundingBox();
    if (!box) throw new Error("The 3D canvas has no size.");

    const inspector = graph.locator(".graph-surface-inspector");
    const positions = [0.3, 0.45, 0.6, 0.75];
    for (const vertical of positions) {
        for (const horizontal of positions) {
            await page.mouse.move(box.x + box.width * horizontal, box.y + box.height * vertical);
            await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
            if (await inspector.isVisible()) return;
        }
    }
    throw new Error("Could not find a visible surface point to inspect.");
}

test("3D graph supports camera views, inspection, and theme rerendering", async ({ page }) => {
    const browserErrors = [];
    page.on("console", message => {
        if (message.type() === "error") browserErrors.push(message.text());
    });
    page.on("pageerror", error => browserErrors.push(error.message));

    await openMathTutor(page);
    const graph = await addSurfaceGraph(page, "Graph z = x^2 + y^2");
    const toolbar = graph.locator(".graph-view-toolbar");
    await expect(toolbar).toHaveAttribute("data-view", "default");

    for (const [label, view] of [["Top", "top"], ["Front", "front"], ["Side", "side"], ["3D", "default"]]) {
        await toolbar.getByText(label, { exact: true }).click();
        await expect(toolbar).toHaveAttribute("data-view", view);
    }

    await page.waitForTimeout(250);
    await hoverAVisibleSurfacePoint(page, graph);
    await expect(graph.locator(".graph-surface-inspector")).toBeVisible();

    await page.locator("#aiSettingsBtn").click();
    await page.locator("#themeToggle").click();
    await page.locator("[data-theme-choice=neon]").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "neon");
    await page.keyboard.press("Escape");
    await expect(graph.locator("canvas")).toHaveCount(1);
    await expect(graph.locator(".graph-view-toolbar")).toHaveCount(1);
    expect(browserErrors).toEqual([]);
});

for (const equation of ["z = 100", "z = -100", "z = x^2 + y^2 + 100"]) {
    test(`shifted ${equation} renders an inspectable surface, not just a grid`, async ({ page }) => {
        await openMathTutor(page);
        const graph = await addSurfaceGraph(page, "Graph " + equation);
        await page.waitForTimeout(300);
        await hoverAVisibleSurfacePoint(page, graph);
        await expect(graph.locator(".graph-surface-inspector")).toBeVisible();
        await graph.getByText("Top", { exact: true }).click();
        await expect(graph.locator(".graph-view-toolbar")).toHaveAttribute("data-view", "top");
        await graph.getByText("Reset", { exact: true }).click();
        await page.waitForTimeout(350);
        await hoverAVisibleSurfacePoint(page, graph);
    });
}

test("shifted 3D graph stays clear of the composer on an iPad-sized screen", async ({ page }, testInfo) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await openMathTutor(page);
    await page.waitForFunction(() => chatHistoryReady && aiSettingsStatus.loaded);
    await page.locator("#userInput").fill("Graph z=100");
    await page.locator("#sendBtn").click();
    const graph = page.locator(".local-graph-container").last();
    await expect(graph.locator("canvas")).toBeVisible();
    await page.waitForFunction(() => !isSending);
    await page.locator("#chatMessages").evaluate(el => el.scrollTo({ top: el.scrollHeight, behavior: "instant" }));
    await hoverAVisibleSurfacePoint(page, graph);
    const before = await graph.locator("canvas").screenshot();
    await graph.getByText("Top", { exact: true }).click();
    await page.waitForTimeout(350);
    expect((await graph.locator("canvas").screenshot()).equals(before)).toBe(false);
    await graph.getByText("Reset", { exact: true }).click();
    await page.waitForTimeout(350);
    await hoverAVisibleSurfacePoint(page, graph);
    const canvas = await graph.locator("canvas").boundingBox();
    const composer = await page.locator(".text-pill").boundingBox();
    expect(canvas.y + canvas.height).toBeLessThanOrEqual(composer.y);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("shifted-3d-ipad.png") });
});

test("3D graph fits a phone screen and preserves Top after a touch inspection", async ({ browser }) => {
    const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
    });
    const page = await context.newPage();

    await openMathTutor(page);
    const graph = await addSurfaceGraph(page, "Graph z = sin(x) * cos(y)");
    const toolbar = graph.locator(".graph-view-toolbar");
    await toolbar.getByText("Top", { exact: true }).click();

    const canvas = graph.locator("canvas");
    const box = await canvas.boundingBox();
    if (!box) throw new Error("The phone 3D canvas has no size.");
    await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);

    await expect(toolbar).toHaveAttribute("data-view", "top");
    await expect(graph.locator(".graph-surface-inspector")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
});

test("a cone and plane system renders as several interactive 3D surfaces", async ({ page }) => {
    await openMathTutor(page);
    const graph = await addSurfaceGraph(page, "z^2 = x^2 + y^2\nz = x + 2");

    await expect(graph.locator("canvas")).toBeVisible();
    await expect(graph.locator(".graph-view-toolbar")).toHaveCount(1);
    const surfaceCount = await graph.evaluate(container => container.graphSpec?.surfaces?.length);
    expect(surfaceCount).toBe(3);
    await hoverAVisibleSurfacePoint(page, graph);
    await expect(graph.locator(".graph-surface-inspector")).toBeVisible();
});
