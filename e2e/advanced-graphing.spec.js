const { expect, test } = require("@playwright/test");

async function openMathTutor(page) {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
}

async function addGraph(page, message) {
    await page.evaluate(async graphMessage => {
        const response = await fetch("/plot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: graphMessage }),
        });
        const graphSpec = await response.json();
        if (!response.ok) throw new Error(graphSpec.error || "Could not create graph data.");

        const container = document.createElement("div");
        container.className = "local-graph-container";
        container.graphSpec = graphSpec;
        document.querySelector("#chatMessages").appendChild(container);
        window.DelphicGraphing.renderGraph(
            container,
            graphSpec,
            document.documentElement.getAttribute("data-theme") || "dark"
        );
    }, message);

    const graph = page.locator(".local-graph-container").last();
    await expect(graph.locator("canvas")).toBeVisible();
    return graph;
}

test("advanced two-dimensional graph types render without browser errors", async ({ page }) => {
    const browserErrors = [];
    page.on("pageerror", error => browserErrors.push(error.message));

    await openMathTutor(page);
    for (const message of [
        "Graph x^2 / 9 + y^2 / 4 = 1",
        "Graph r = 2sin(3theta)",
        "Graph x = cos(t), y = sin(t)",
        "Graph y = x^2 for x >= 0; y = -x for x < 0",
        "Graph x^2 + y^2 <= 25",
        "Graph vector field <y, -x>",
    ]) {
        await addGraph(page, message);
    }

    await expect(page.locator(".local-graph-container canvas")).toHaveCount(6);
    expect(browserErrors).toEqual([]);
});

test("implicit surfaces, 3D curves, and systems render with view controls", async ({ page }) => {
    const browserErrors = [];
    page.on("pageerror", error => browserErrors.push(error.message));

    await openMathTutor(page);
    const sphere = await addGraph(page, "Graph x^2 + y^2 + z^2 = 16");
    const curve = await addGraph(page, "Graph x = cos(t), y = sin(t), z = t / 2");
    const system = await addGraph(page, "z^2 = x^2 + y^2\nz = x + 2");

    await expect(sphere.locator(".graph-view-toolbar")).toHaveCount(1);
    await expect(curve.locator(".graph-view-toolbar")).toHaveCount(1);
    await expect(system.locator(".graph-view-toolbar")).toHaveCount(1);
    await system.locator(".graph-view-toolbar").getByText("Top", { exact: true }).click();
    await expect(system.locator(".graph-view-toolbar")).toHaveAttribute("data-view", "top");
    expect(browserErrors).toEqual([]);
});
