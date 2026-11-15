const { test, expect } = require("@playwright/test");

const mathAnswer = [
    "## Keep both sides balanced",
    "Subtract 4 from both sides, then divide by 2.",
    "1. Start with \\(2x + 4 = 10\\).\n2. Subtract 4: \\(2x = 6\\).\n3. Divide by 2: \\(x = 3\\).",
    "> The first incorrect step was subtracting 4 from only one side. Both sides must stay equal.",
    "$$\\frac{2x+4-4}{2} = \\frac{10-4}{2}$$",
    "| " + Array.from({ length: 9 }, (_, i) => `Trial ${i + 1} measurements`).join(" | ") + " |\n| " + "--- | ".repeat(9) + "\n| " + "123.456 | ".repeat(9),
    "```text\n" + "long_code_example_".repeat(30) + "\n```",
    "[Read more](https://example.com/math) and " + "longword".repeat(50),
    "<img src=x onerror=alert(1)><script>alert(1)</script>",
    "CONFIDENCE: Medium",
].join("\n\n");

const diagram = {
    version: 1, type: "force_diagram", title: "Forces on a box",
    description: "Weight pulls down; the normal force points up.",
    objects: [
        { id: "box", kind: "box", x: 38, y: 37, width: 24, height: 20, label: "Box" },
        { id: "normal", kind: "arrow", x1: 50, y1: 37, x2: 50, y2: 9, label: "Normal force" },
        { id: "weight", kind: "arrow", x1: 50, y1: 57, x2: 50, y2: 85, label: "Weight" },
    ],
};

const scienceAnswer = [
    "## Why this answer needs another look",
    "**The mantle is directly below Earth's crust, not the outer core.**",
    "The layers from outside to inside are crust, mantle, outer core, and inner core.",
    "Your answer, outer core, skips the mantle. Try identifying which layer touches the bottom of the crust.",
    "CONFIDENCE: High",
].join("\n\n");

function stream(text, metadata = {}) {
    return "event: token\ndata: " + JSON.stringify({ text }) + "\n\nevent: complete\ndata: "
        + JSON.stringify({ tokens_used: 5, finish_reason: "complete", ...metadata }) + "\n\n";
}

async function mockWorkspace(page, mode, messages = [], sessionId = "conversation-test") {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: sessionId, messages, images: [], tokens_used: 0,
    } }));
    await page.route("**/sessions", route => route.fulfill({ json: {
        current_session_id: sessionId, sessions: [],
    } }));
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 0 } }));
    await page.goto(mode === "science" ? "/science" : "/#tutor");
}

async function assertNoOverflow(page) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await page.locator("#chatMessages").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
}

async function assertReadableContrast(reply) {
    const ratios = await reply.evaluate(el => {
        const probe = document.createElement("div");
        probe.style.backgroundColor = "var(--entry-surface)";
        el.appendChild(probe);
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d");
        const rgb = value => {
            context.fillStyle = value;
            context.fillRect(0, 0, 1, 1);
            return [...context.getImageData(0, 0, 1, 1).data].slice(0, 3);
        };
        const luminance = values => values.map(v => v / 255).map(v => v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4)
            .reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
        const background = luminance(rgb(getComputedStyle(probe).backgroundColor));
        probe.remove();
        return [".message-content", ".message-role", ".message-time", ".confidence-badge", ".response-actions button", ".study-reference"]
            .map(selector => el.querySelector(selector)).filter(Boolean).map(node => {
                const foreground = luminance(rgb(getComputedStyle(node).color));
                return (Math.max(background, foreground) + .05) / (Math.min(background, foreground) + .05);
            });
    });
    for (const ratio of ratios) expect(ratio).toBeGreaterThanOrEqual(4.5);
}

for (const mode of ["math", "science"]) {
    test(`${mode} conversations have unframed answers, clear roles, safe overflow, and readable actions`, async ({ page }, testInfo) => {
        const errors = [];
        page.on("pageerror", error => errors.push(error.message));
        const content = mode === "math" ? mathAnswer : scienceAnswer;
        await mockWorkspace(page, mode, [
            { role: "user", content: mode === "math" ? "Can you check my work?\n2x + 4 = 10" : "I chose outer core. Why is it wrong?" },
            { id: 8, role: "assistant", content, finish_reason: "length", can_continue: true,
                sources: [{ title: "Class notes", excerpt: "<img src=x> Keep both sides balanced." }],
                ...(mode === "science" ? { diagram } : {}) },
        ]);
        const reply = page.locator(".message.assistant").last();
        await expect(reply.locator(".message-role")).toHaveText("Delphic AI");
        await expect(page.locator(".message.user .message-role")).toHaveText("You");
        await expect(reply.locator(".response-actions > button")).toHaveCount(3);
        await expect(reply.locator(".message-content img, .message-content script")).toHaveCount(0);
        if (mode === "math") {
            await expect(reply.locator(".katex").first()).toBeVisible();
            await expect(reply.getByText("The first incorrect step", { exact: false })).toBeVisible();
            await expect(reply.locator(".message-table-scroll table")).toHaveCount(1);
            await expect(reply.locator(".message-content a")).toHaveAttribute("href", "https://example.com/math");
        } else {
            await expect(reply.getByText("The mantle is directly below", { exact: false })).toBeVisible();
            await expect(reply.locator(".science-diagram svg")).toBeVisible();
            expect(await reply.locator(".science-diagram").evaluate(el => el.nextElementSibling.className)).toBe("response-actions");
        }
        for (const viewport of [
            { width: 1440, height: 900 }, { width: 1024, height: 768 },
            { width: 768, height: 1024 }, { width: 390, height: 844 }, { width: 320, height: 640 },
        ]) {
            await page.setViewportSize(viewport);
            for (const theme of ["light", "dark", "neon"]) {
                await page.evaluate(value => document.documentElement.setAttribute("data-theme", value), theme);
                expect(await reply.locator(".message-content").evaluate(el => {
                    const style = getComputedStyle(el);
                    return [style.backgroundColor, style.borderTopWidth, style.boxShadow];
                })).toEqual(["rgba(0, 0, 0, 0)", "0px", "none"]);
                await assertNoOverflow(page);
                await assertReadableContrast(reply);
                for (const button of await reply.locator(".response-actions button").all()) {
                    const box = await button.boundingBox();
                    // DOMRect can be a fraction below the CSS size after resizing.
                    expect(Math.round(box.height * 100) / 100).toBeGreaterThanOrEqual(44);
                    expect(box.x).toBeGreaterThanOrEqual(0);
                    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
                }
                if (mode === "math" && viewport.width <= 390) {
                    expect(await reply.locator(".message-table-scroll").evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true);
                    await reply.locator(".message-table-scroll").focus();
                    await page.keyboard.press("ArrowRight");
                    await expect.poll(() => reply.locator(".message-table-scroll").evaluate(el => el.scrollLeft)).toBeGreaterThan(0);
                }
                await page.locator("#chatMessages").evaluate(el => el.scrollTo({ top: 0, behavior: "instant" }));
                if ([1440, 390].includes(viewport.width)) {
                    const toolbar = page.locator(".entry-toolbar");
                    const before = await toolbar.screenshot({ animations: "disabled" });
                    await page.locator("#chatMessages").evaluate(el => { el.style.visibility = "hidden"; });
                    const withoutMessages = await toolbar.screenshot({ animations: "disabled" });
                    await page.locator("#chatMessages").evaluate(el => { el.style.visibility = ""; });
                    const changed = await page.evaluate(async images => {
                        const pixels = await Promise.all(images.map(async base64 => {
                            const image = new Image();
                            image.src = "data:image/png;base64," + base64;
                            await image.decode();
                            const canvas = document.createElement("canvas");
                            canvas.width = image.width;
                            canvas.height = image.height;
                            const context = canvas.getContext("2d");
                            context.drawImage(image, 0, 0);
                            return context.getImageData(0, 0, canvas.width, canvas.height);
                        }));
                        const [a, b] = pixels;
                        if (a.width !== b.width || a.height !== b.height) return -1;
                        let different = 0;
                        for (let i = 0; i < a.data.length; i += 4) {
                            // Ignore tiny edge-antialias changes from compositor layer removal.
                            if ([0, 1, 2].some(channel => Math.abs(a.data[i + channel] - b.data[i + channel]) > 20)) different++;
                        }
                        return different;
                    }, [before.toString("base64"), withoutMessages.toString("base64")]);
                    if (changed !== 0) {
                        await testInfo.attach("toolbar-with-messages", { body: before, contentType: "image/png" });
                        await testInfo.attach("toolbar-without-messages", { body: withoutMessages, contentType: "image/png" });
                    }
                    expect(changed).toBe(0);
                }
                await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-${theme}-top.png`), animations: "disabled" });
                await reply.locator(".response-actions").scrollIntoViewIfNeeded();
                await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-${theme}.png`), animations: "disabled" });
            }
        }
        await reply.locator(".study-reference summary").focus();
        await page.keyboard.press("Enter");
        await expect(reply.locator(".study-reference blockquote")).toContainText("<img src=x>");
        await expect(reply.locator(".study-reference img")).toHaveCount(0);
        expect(errors).toEqual([]);
    });
}

test("Copy is keyboard accessible, copies continued raw math, and reports clipboard failure", async ({ page }) => {
    await page.addInitScript(() => {
        Object.defineProperty(navigator, "clipboard", { configurable: true, value: {
            writeText: async text => {
                if (window.failCopy) throw new Error("Clipboard unavailable");
                window.copiedAnswer = text;
            },
        } });
    });
    await mockWorkspace(page, "math", [{
        id: 8, role: "assistant", content: "Partial answer.", finish_reason: "length", can_continue: true,
    }]);
    const completed = "Partial answer. The result is \\(x = 3\\).\nCONFIDENCE: High";
    await page.route("**/responses/continue", route => route.fulfill({ json: {
        reply: completed, finish_reason: "complete", continuation_count: 1,
        message_id: 8, session_id: "conversation-test", can_continue: false,
    } }));
    const reply = page.locator(".message.assistant").last();
    await reply.getByRole("button", { name: "Continue response", exact: true }).click();
    await expect(reply.getByRole("status")).toHaveText("Response completed");
    const copy = reply.getByRole("button", { name: "Copy response", exact: true });
    await copy.focus();
    await page.keyboard.press("Enter");
    await expect(reply.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
    expect(await page.evaluate(() => window.copiedAnswer)).toBe(completed.split("\nCONFIDENCE")[0]);
    await page.evaluate(() => { window.failCopy = true; });
    await expect(copy).toBeVisible();
    await copy.click();
    await expect(page.locator(".input-warning")).toContainText("Could not copy this response");
    await expect(reply.locator(".message-content")).toContainText("The result is");
});

test("loading and partial streaming remain readable and finish in the same action row", async ({ page }) => {
    await mockWorkspace(page, "math");
    let release;
    const ready = new Promise(resolve => { release = resolve; });
    await page.route("**/stream", async route => {
        await ready;
        await route.fulfill({ contentType: "text/event-stream", body: stream("A guided explanation. " + "Keep both sides balanced. ".repeat(70)) });
    });
    await page.locator("#userInput").fill("Explain solving an equation");
    await page.locator("#sendBtn").click();
    await expect(page.getByRole("status", { name: "" }).filter({ hasText: "Thinking..." })).toBeVisible();
    release();
    const reply = page.locator(".message.assistant").last();
    await expect(reply).toHaveAttribute("aria-busy", "true");
    await expect(reply.locator(".message-text")).toContainText("A guided explanation.");
    await reply.locator(".response-actions").evaluate(el => { el.dataset.identity = "original"; });
    await expect(reply.locator(".copy-btn")).toBeHidden();
    await expect(reply).toHaveAttribute("aria-busy", "false");
    await expect(reply.locator(".response-actions")).toHaveAttribute("data-identity", "original");
    await expect(reply.locator(".copy-btn")).toBeVisible();
    await expect(page.locator("#typingIndicator")).toHaveCount(0);
});

test("an EOF without metadata keeps partial content and labels its unknown completion", async ({ page }) => {
    await mockWorkspace(page, "math");
    await page.route("**/stream", route => route.fulfill({ contentType: "text/event-stream", body: "data: Preserve this partial explanation.\n\n" }));
    await page.locator("#userInput").fill("Explain equality");
    await page.locator("#sendBtn").click();
    const reply = page.locator(".message.assistant").last();
    await expect(reply).toHaveAttribute("aria-busy", "false");
    await expect(reply.locator(".message-content")).toContainText("Preserve this partial explanation.");
    await expect(reply.getByRole("status")).toHaveText("Response ended without a completion status.");
    await expect(reply.getByRole("button", { name: "Copy response" })).toBeVisible();
});

test("a broken stream preserves its partial answer, shows interruption, and clears busy state", async ({ page }) => {
    await mockWorkspace(page, "math");
    await page.evaluate(() => {
        const originalFetch = window.fetch;
        window.fetch = (url, options) => {
            if (!String(url).endsWith("/stream")) return originalFetch(url, options);
            return Promise.resolve(new Response(new ReadableStream({
                start(controller) {
                    controller.enqueue(new TextEncoder().encode("data: The first step is to subtract four from both sides of the equation.\n\n"));
                    setTimeout(() => controller.error(new Error("Connection lost")), 60);
                },
            }), { headers: { "Content-Type": "text/event-stream" } }));
        };
    });
    await page.locator("#userInput").fill("Explain this equation");
    await page.locator("#sendBtn").click();
    const partial = page.locator(".message.assistant").filter({ hasText: "The first step is" });
    await expect(partial).toHaveAttribute("aria-busy", "false");
    await expect(partial.locator(".message-content")).toContainText("both sides of the equation.");
    await expect(partial.getByRole("status")).toHaveText("Response interrupted");
    await expect(partial.getByRole("button", { name: "Copy response" })).toBeVisible();
    await expect(page.locator(".message.assistant").last()).toContainText("Network error");
    await expect(page.locator("#sendBtn")).toBeEnabled();
});

for (const mode of ["math", "science"]) {
    test(`${mode} downloads preserve learning content and location instructions`, async ({ page, context }) => {
        const messages = [{ role: "user", content: "Explain this" }, {
            id: 8, role: "assistant", content: mode === "math" ? mathAnswer : scienceAnswer,
            sources: [{ title: "Class notes", excerpt: "<img src=x> Reviewed notes." }],
            ...(mode === "science" ? { diagram } : {}),
        }];
        await mockWorkspace(page, mode, messages);
        await page.route("**/sessions", route => route.fulfill({ json: {
            current_session_id: "conversation-test", sessions: [{
                session_id: "past-chat", preview: "Reviewed learning", message_count: 2, title_generated: true,
            }],
        } }));
        await page.route("**/sessions/messages", route => route.fulfill({ json: { messages, images: [] } }));
        await page.reload();
        await page.getByRole("button", { name: "More actions for Reviewed learning", exact: true }).click();
        const pending = page.waitForEvent("download");
        await page.getByRole("menuitem", { name: "Download chat", exact: true }).click();
        const download = await pending;
        expect(download.suggestedFilename()).toMatch(new RegExp(`^delphic-${mode}-chat-.*\\.html$`));
        await expect(page.locator(".download-help")).toContainText("File Explorer on Windows or Finder on Mac");
        await expect(page.locator(".download-help")).toContainText("folder you selected");
        const html = await page.evaluate(messages => buildTranscriptHtml(messages), messages);
        expect(html).not.toContain("response-actions");
        const exported = await context.newPage();
        await exported.setViewportSize({ width: 390, height: 844 });
        await exported.setContent(html);
        await expect(exported.locator(".bubble script, .bubble img")).toHaveCount(0);
        if (mode === "math") {
            await expect(exported.locator("math").first()).toBeVisible();
            await expect(exported.locator(".message-table-scroll table")).toHaveCount(1);
            await expect(exported.locator("pre")).toContainText("long_code_example_");
        } else {
            await expect(exported.locator(".bubble")).toContainText(["Explain this", "outer core, skips the mantle"]);
            await expect(exported.locator(".science-diagram svg")).toBeVisible();
        }
        expect(await exported.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        await exported.close();
    });
}

for (const mode of ["math", "science"]) {
    test(`${mode} Practice keeps existing request flags and icons after completion`, async ({ page }) => {
        await mockWorkspace(page, mode, [{ role: "assistant", content: "Here is an explanation." }]);
        let payload;
        await page.route("**/stream", route => {
            payload = route.request().postDataJSON();
            return route.fulfill({ contentType: "text/event-stream", body: stream("A practice question.") });
        });
        const practice = page.locator(".practice-btn").first();
        const label = await practice.innerText();
        await practice.click();
        await expect.poll(() => payload?.practice_mode).toBe(true);
        expect(payload.quiz_mode).toBe(false);
        await expect(practice).toBeEnabled();
        await expect(practice).toHaveText(label);
        await expect(practice.locator("svg use")).toHaveAttribute("href", /#pencil-line$/);
    });
}

test("Science quiz corrections and explanations are visible without disclosure controls", async ({ page }) => {
    await mockWorkspace(page, "science");
    await page.route("**/stream", route => route.fulfill({ contentType: "text/event-stream", body: stream(scienceAnswer) }));
    await page.locator("#userInput").fill("I chose outer core for the layer below the crust.");
    await page.locator("#sendBtn").click();
    const reply = page.locator(".message.assistant").last();
    await expect(reply).toHaveAttribute("aria-busy", "false");
    await expect(reply.locator(".message-content")).toContainText("Your answer, outer core, skips the mantle.");
    await expect(reply.locator(".message-content details")).toHaveCount(0);
});

// Decode the browser's canvas screenshot, not a WebGL buffer cleared after rendering.
async function canvasPixels(page, canvas) {
    const png = await canvas.screenshot();
    return page.evaluate(async base64 => {
        const image = new Image();
        image.src = "data:image/png;base64," + base64;
        await image.decode();
        const sample = document.createElement("canvas");
        sample.width = image.width;
        sample.height = image.height;
        const context = sample.getContext("2d");
        context.drawImage(image, 0, 0);
        const { data, width, height } = context.getImageData(0, 0, sample.width, sample.height);
        let colorful = 0, total = 0, hash = 2166136261;
        for (let y = Math.floor(height * .25); y < height * .9; y += 2) {
            for (let x = Math.floor(width * .1); x < width * .9; x += 2) {
                const i = (y * width + x) * 4;
                const r = data[i], g = data[i + 1], b = data[i + 2];
                if (Math.max(r, g, b) - Math.min(r, g, b) > 55 && Math.max(r, g, b) > 100) colorful++;
                hash = Math.imul(hash ^ (r << 16 | g << 8 | b), 16777619) >>> 0;
                total++;
            }
        }
        return { colorful, fraction: colorful / total, hash, width, height };
    }, png.toString("base64"));
}

test("real 2D and 3D graphs stay nonblank, framed, and interactive through sidebar and phone resizing", async ({ page }, testInfo) => {
    test.setTimeout(60_000);
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    const ownedChat = await (await page.request.get("/history")).json();
    await mockWorkspace(page, "math", [], ownedChat.session_id);
    await page.route("**/stream", route => route.fulfill({ contentType: "text/event-stream", body: stream("Here is your graph.") }));
    for (const [index, equation] of ["Graph y = x^2 - 4", "Graph y = x^(1/3)", "Graph z = sin(x) * cos(y)"].entries()) {
        await page.locator("#userInput").fill(equation);
        await page.locator("#sendBtn").click();
        await expect(page.locator(".local-graph-container")).toHaveCount(index + 1);
        const graph = page.locator(".local-graph-container").last();
        await expect(graph.locator("canvas")).toBeVisible();
        await graph.scrollIntoViewIfNeeded();
        await expect.poll(async () => (await canvasPixels(page, graph.locator("canvas"))).colorful).toBeGreaterThan(25);
        if (equation.includes("1/3")) {
            expect(await graph.evaluate(container => container.graphSpec.series.some(series =>
                series.segments.some(segment => segment.some(([x]) => x < 0))))).toBe(true);
        }
    }
    const graph = page.locator(".local-graph-container").last();
    const canvas = graph.locator("canvas");
    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 320, height: 640 }]) {
        await page.setViewportSize(viewport);
        if (viewport.width <= 768) {
            await expect.poll(async () => {
                const sidebar = await page.locator("#sidebar").boundingBox();
                return sidebar ? sidebar.x + sidebar.width : 0;
            }).toBeLessThanOrEqual(1);
        }
        await page.locator("#chatMessages").evaluate(el => el.scrollTo({ top: el.scrollHeight, behavior: "instant" }));
        await expect.poll(async () => (await canvasPixels(page, canvas)).fraction).toBeGreaterThan(.02);
        const graphBox = await graph.boundingBox();
        const canvasBox = await canvas.boundingBox();
        expect(Math.abs(canvasBox.width - graphBox.width)).toBeLessThanOrEqual(2);
        expect(Math.abs(canvasBox.height - graphBox.height)).toBeLessThanOrEqual(2);
        const composer = await page.locator(".text-pill").boundingBox();
        expect(canvasBox.y + canvasBox.height).toBeLessThanOrEqual(composer.y);
        await assertNoOverflow(page);
        await page.screenshot({ path: testInfo.outputPath(`graph-${viewport.width}.png`) });
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    const handle = page.locator("#sidebarResizeHandle");
    await handle.focus();
    await page.keyboard.press("End");
    await graph.scrollIntoViewIfNeeded();
    await expect.poll(async () => (await canvasPixels(page, canvas)).fraction).toBeGreaterThan(.02);
    await handle.focus();
    await page.keyboard.press("Home");
    await graph.scrollIntoViewIfNeeded();
    await expect.poll(async () => (await canvasPixels(page, canvas)).fraction).toBeGreaterThan(.02);
    const before = await canvasPixels(page, canvas);
    await graph.locator(".graph-view-btn", { hasText: /^Top$/ }).click();
    await page.waitForTimeout(350);
    const top = await canvasPixels(page, canvas);
    expect(top.hash).not.toBe(before.hash);
    expect(top.fraction).toBeGreaterThan(.02);
    await graph.locator(".graph-view-btn", { hasText: /^3D$/ }).click();
    await page.waitForTimeout(350);
    const box = await canvas.boundingBox();
    await page.mouse.move(box.x + box.width * .5, box.y + box.height * .6);
    const beforeDrag = await canvasPixels(page, canvas);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * .65, box.y + box.height * .7, { steps: 8 });
    await page.mouse.up();
    await page.waitForTimeout(350);
    expect((await canvasPixels(page, canvas)).hash).not.toBe(beforeDrag.hash);
    expect(errors).toEqual([]);
});
