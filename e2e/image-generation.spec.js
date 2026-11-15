const { test, expect } = require("@playwright/test");
const fs = require("fs");
const { execFileSync } = require("child_process");

const IMAGE_ID = "11111111-1111-4111-8111-111111111111";
const PNG = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M/wHwAF/gL+XxKqWQAAAABJRU5ErkJggg==",
    "base64",
);

async function openMathTutor(page) {
    await page.goto("/");
    await page.locator(".home-actions [data-start-tutor]").click();
    await expect(page.locator("#imageModeBtn")).toBeVisible();
}

function imagePayload(prompt, mode = "educational_visual") {
    return {
        session_id: "math-session",
        message: {
            id: 42,
            role: "assistant",
            content: "Here is the AI-generated image. Check important details before using it.",
            finish_reason: "complete",
        },
        image: {
            id: IMAGE_ID,
            message_id: 42,
            prompt,
            mode,
            width: 1024,
            height: 1024,
            mime_type: "image/png",
            review_passed: true,
            safety_problem: false,
            url: `/images/${IMAGE_ID}`,
            download_url: `/images/${IMAGE_ID}?download=1`,
        },
        attempt_count: 1,
        review_passed: true,
        cost_usd: 0.01,
    };
}

test.beforeEach(async ({ page }) => {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured: true, provider: "groq", model: "test", providers: [],
    } }));
    await page.route(`**/images/${IMAGE_ID}*`, async route => {
        if (route.request().method() === "DELETE") {
            await route.fulfill({ status: 200, json: { deleted_image_id: IMAGE_ID } });
            return;
        }
        await route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    });
});

test("adult-development image UI can create, edit, and delete a mocked image", async ({ page }) => {
    let sentRequest;
    await page.route("**/images/generate", async route => {
        sentRequest = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: imagePayload(sentRequest.prompt, sentRequest.mode) });
    });

    await openMathTutor(page);
    await page.locator("#imageModeBtn").click();
    await expect(page.locator("#imageModeSelect")).toBeVisible();
    await page.locator("#imageModeSelect").selectOption("creative_illustration");
    await page.locator("#userInput").fill("A colorful visual showing the parts of a parabola");
    await page.locator("#sendBtn").click();

    await expect(page.locator(".generated-image-card img")).toHaveAttribute(
        "alt",
        /AI-generated creative illustration.*parts of a parabola/i,
    );
    await expect(page.getByText("AI-generated", { exact: true })).toBeVisible();
    expect(sentRequest.area).toBe("math");
    expect(sentRequest.mode).toBe("creative_illustration");

    await page.getByRole("button", { name: "Edit prompt" }).click();
    await expect(page.locator("#userInput")).toHaveValue(sentRequest.prompt);
    await expect(page.locator("#imageModeSelect")).toHaveValue("creative_illustration");

    await page.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("Image deleted", { exact: true })).toBeVisible();
    await expect(page.locator(".generated-image-card")).toHaveCount(0);
});

test("saved image returns with its chat after page load", async ({ page }) => {
    const prompt = "A clear educational visual of a triangle";
    const historyOwners = [];
    const imageOwners = [];
    await page.route("**/history", route => route.fulfill({
        status: 200,
        json: (() => {
            historyOwners.push(route.request().headers()["x-delphic-corpus-owner"] || "");
            return {
                session_id: "math-session",
                tokens_used: 0,
                messages: [
                    { id: 41, role: "user", content: prompt },
                    { id: 42, role: "assistant", content: "Here is the saved AI-generated image." },
                ],
                images: [imagePayload(prompt).image],
            };
        })(),
    }));
    await page.route(`**/images/${IMAGE_ID}`, route => {
        imageOwners.push(route.request().headers()["x-delphic-corpus-owner"] || "");
        return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    });

    await openMathTutor(page);
    await expect(page.locator(".generated-image-card img")).toBeVisible();
    await expect(page.locator(".generated-image-prompt")).toHaveText(prompt);

    await page.reload();
    await expect(page.locator(".generated-image-card")).toHaveCount(1);
    await expect(page.locator(".generated-image-card img")).toBeVisible();
    await expect(page.locator(".generated-image-prompt")).toHaveText(prompt);

    expect(historyOwners).toHaveLength(2);
    expect(imageOwners.length).toBeGreaterThanOrEqual(2);
    expect(new Set(historyOwners).size).toBe(1);
    expect(new Set(imageOwners)).toEqual(new Set(historyOwners));
    expect(historyOwners[0]).toMatch(/^[0-9a-f-]{36}$/i);
});

test("science tutor sends science as the image subject area", async ({ page }) => {
    let sentRequest;
    await page.route("**/images/generate", async route => {
        sentRequest = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: imagePayload(sentRequest.prompt, sentRequest.mode) });
    });

    await page.goto("/science");
    await page.locator("#imageModeBtn").click();
    await page.locator("#userInput").fill("A clear educational visual of a plant cell");
    await page.locator("#sendBtn").click();
    await expect(page.locator(".generated-image-card")).toBeVisible();
    expect(sentRequest.area).toBe("science");
});

test("an explicit realistic picture request generates on the first send", async ({ page }) => {
    let sentRequest = null;
    await page.route("**/images/generate", async route => {
        sentRequest = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: imagePayload(sentRequest.prompt, sentRequest.mode) });
    });

    await page.goto("/science");
    const prompt = "Create a realistic picture of a labeled amoeba";
    await page.locator("#userInput").fill(prompt);
    await page.locator("#sendBtn").click();

    await expect(page.locator(".generated-image-card")).toBeVisible();
    expect(sentRequest.prompt).toBe(prompt);
    expect(sentRequest.mode).toBe("realistic_image");
    expect(sentRequest.area).toBe("science");
});

for (const path of ["/#tutor", "/science"]) {
    for (const start of ["Create", "Draw", "Sketch", "Could you please draw"]) {
        test(`${path} ${start} a picture selects image generation on the first send`, async ({ page }) => {
            let sent;
            const wrongRequests = [];
            await page.route(/\/(?:plot|stream|science\/stream)$/, route => {
                wrongRequests.push(route.request().url());
                return route.abort();
            });
            await page.route("**/images/generate", route => {
                sent = route.request().postDataJSON();
                return route.fulfill({ status: 201, json: imagePayload(sent.prompt, sent.mode) });
            });
            await page.goto(path);
            const prompt = `${start} a realistic picture of a labeled amoeba`;
            await page.locator("#userInput").fill(prompt);
            await page.locator("#sendBtn").click();
            await expect(page.locator(".generated-image-card img")).toBeVisible();
            expect(sent.prompt).toBe(prompt);
            expect(sent.mode).toBe("realistic_image");
            expect(wrongRequests).toEqual([]);
        });
    }
    test(`${path} equations keep graph priority over picture wording`, async ({ page }) => {
        await page.goto(path);
        const results = await page.evaluate(() => [
            "Draw the graph y = x^2", "Sketch z = x^2 + y^2", "Create a picture of the graph y=x",
            "Plot sin(x)", "Graph vector field <y,-x>",
        ].map(text => ({ graph: isGraphRequest(text), image: looksLikeImageGenerationRequest(text) })));
        expect(results.every(result => result.graph && !result.image)).toBe(true);
    });
}

test("Draw and Sketch free Science diagrams do not buy generated images", async ({ page }) => {
    await page.goto("/science");
    const results = await page.evaluate(() => ["Draw a plant cell diagram", "Sketch a force diagram"].map(text => ({
        graph: isGraphRequest(text), image: looksLikeImageGenerationRequest(text), local: isSupportedLocalScienceDiagramRequest(text),
    })));
    expect(results.every(result => !result.graph && !result.image && result.local)).toBe(true);
});

test("a heart image request uses image generation instead of science text chat", async ({ page }) => {
    let sentRequest = null;
    let textRequests = 0;
    await page.route("**/science/stream", route => {
        textRequests += 1;
        return route.abort();
    });
    await page.route("**/images/generate", async route => {
        sentRequest = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: imagePayload(sentRequest.prompt, sentRequest.mode) });
    });

    await page.goto("/science");
    const prompt = "Make an image of a heart";
    await page.locator("#userInput").fill(prompt);
    await page.locator("#sendBtn").click();

    await expect(page.locator(".generated-image-card img")).toBeVisible();
    expect(sentRequest.prompt).toBe(prompt);
    expect(sentRequest.area).toBe("science");
    expect(sentRequest.mode).toBe("educational_visual");
    expect(textRequests).toBe(0);
});

test("disabled images explain the limitation and preserve the prompt without calling AI", async ({ page }) => {
    await page.route("**/science", async route => {
        const response = await route.fetch();
        const html = (await response.text()).replace(
            'data-image-generation-enabled="true"',
            'data-image-generation-enabled="false"',
        );
        await route.fulfill({ response, body: html });
    });
    const providerRequests = [];
    await page.route(/\/(?:images\/generate|science\/stream)$/, route => {
        providerRequests.push(route.request().url());
        return route.abort();
    });

    await page.goto("/science");
    const prompt = "Make an image of a heart";
    await page.locator("#userInput").fill(prompt);
    await page.locator("#sendBtn").click();

    await expect(page.getByText(/Image generation is disabled in this installation/)).toBeVisible();
    await expect(page.locator("#userInput")).toHaveValue(prompt);
    expect(providerRequests).toEqual([]);
});

test("a supported free science diagram stays in normal tutor mode", async ({ page }) => {
    let streamedMessage = null;
    await page.route("**/science/stream", async route => {
        streamedMessage = route.request().postDataJSON()?.message;
        await route.fulfill({
            status: 200,
            contentType: "text/event-stream",
            body: [
                "data: Here is the reviewed local diagram.\n\n",
                "event: complete\n",
                'data: {"tokens_used":1,"finish_reason":"complete","can_continue":false}\n\n',
                "data: [DONE:1]\n\n",
            ].join(""),
        });
    });

    await page.goto("/science");
    const prompt = "Show me a picture of a plant cell";
    await page.locator("#userInput").fill(prompt);
    await page.locator("#sendBtn").click();

    await expect.poll(() => streamedMessage).toBe(prompt);
    await expect(page.locator("#imageModeBtn")).toHaveAttribute("aria-pressed", "false");
});

test("cancel stops waiting and preserves the request for a safe retry", async ({ page }) => {
    await page.route("**/images/generate", async route => {
        await new Promise(resolve => setTimeout(resolve, 1000));
        await route.fulfill({ status: 201, json: imagePayload("A solar system illustration") });
    });

    await openMathTutor(page);
    await page.locator("#imageModeBtn").click();
    await page.locator("#userInput").fill("A solar system illustration");
    await page.locator("#sendBtn").click();
    await page.getByRole("button", { name: "Cancel" }).click();

    await expect(page.getByText("Image not ready", { exact: true })).toBeVisible();
    await expect(page.getByText(/without buying a duplicate/i)).toBeVisible();
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

for (const area of ["math", "science"]) {
    test(`${area} image loading, retry, and result follow the current workspace theme`, async ({ page }) => {
        test.setTimeout(60_000);
        let release;
        const pending = new Promise(resolve => { release = resolve; });
        let requests = 0;
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.route("**/images/generate", async route => {
            requests += 1;
            if (requests === 1) {
                await pending;
                await route.fulfill({ status: 503, json: { error: "The image service is temporarily unavailable." } });
            } else {
                const data = route.request().postDataJSON();
                await route.fulfill({ status: 201, json: imagePayload(data.prompt, data.mode) });
            }
        });

        await page.goto(area === "science" ? "/science" : "/#tutor");
        await page.locator("#userInput").fill("Make an image of a human heart");
        await page.locator("#sendBtn").click();
        const status = page.locator(".image-generation-status");
        await expect(status).toBeVisible();

        try {
            for (const width of [1440, 390, 320]) {
                await page.setViewportSize({ width, height: 900 });
                for (const [theme, accent] of [["light"], ["dark"], ["neon", "Purple"], ["neon", "Orange"], ["neon", "Green"]]) {
                    await page.locator("#aiSettingsBtn").click();
                    await page.locator("#themeToggle").click();
                    await page.locator(`[data-theme-choice="${theme}"]`).click();
                    if (accent) await page.getByRole("radio", { name: accent, exact: true }).check();
                    await page.keyboard.press("Escape");
                    const colors = await status.evaluate(el => {
                        const style = getComputedStyle(el);
                        const canvas = document.createElement("canvas");
                        canvas.width = canvas.height = 1;
                        const ctx = canvas.getContext("2d");
                        const rgb = color => {
                            ctx.clearRect(0, 0, 1, 1);
                            ctx.fillStyle = color;
                            ctx.fillRect(0, 0, 1, 1);
                            return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
                        };
                        const token = name => rgb(style.getPropertyValue(name));
                        const luminance = values => values.map(v => {
                            const s = v / 255;
                            return s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4;
                        }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
                        const bg = rgb(style.backgroundColor);
                        const contrast = color => {
                            const a = luminance(rgb(color)), b = luminance(bg);
                            return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
                        };
                        return {
                            background: bg, surface: token("--entry-surface"),
                            border: rgb(style.borderTopColor), line: token("--entry-line"),
                            spinner: rgb(getComputedStyle(el.querySelector(".image-generation-spinner")).borderTopColor),
                            accent: token("--entry-accent"),
                            contrast: [el.querySelector("strong"), el.querySelector(":scope > div > span"), el.querySelector("button")]
                                .map(node => contrast(getComputedStyle(node).color)),
                        };
                    });
                    expect(colors.background).toEqual(colors.surface);
                    expect(colors.border).toEqual(colors.line);
                    expect(colors.spinner).toEqual(colors.accent);
                    for (const ratio of colors.contrast) expect(ratio).toBeGreaterThanOrEqual(4.5);
                    await expect(page.locator(".image-generation-spinner")).toHaveCSS("animation-name", "none");
                    const box = await status.boundingBox();
                    const cancel = await status.getByRole("button", { name: "Cancel" }).boundingBox();
                    expect(box.x).toBeGreaterThanOrEqual(0);
                    expect(box.x + box.width).toBeLessThanOrEqual(width);
                    expect(cancel.height).toBeGreaterThanOrEqual(44);
                    expect(cancel.x).toBeGreaterThanOrEqual(box.x);
                    expect(cancel.x + cancel.width).toBeLessThanOrEqual(box.x + box.width);
                    if (theme === "dark" || (accent === "Purple" && width === 390)) {
                        await page.screenshot({ path: `/tmp/delphic-image-loading-${area}-${theme}-${width}.png`, animations: "disabled" });
                    }
                }
            }
        } finally {
            release();
        }

        await expect(status).toHaveClass(/has-error/);
        expect(await status.evaluate(el => {
            const probe = document.createElement("span");
            probe.style.color = "var(--tool-danger)";
            el.appendChild(probe);
            const matches = getComputedStyle(el).borderTopColor === getComputedStyle(probe).color;
            probe.remove();
            return matches;
        })).toBe(true);
        await status.getByRole("button", { name: "Retry" }).click();
        await expect(page.locator(".generated-image-card img")).toBeVisible();
        expect(requests).toBe(2);
        const card = page.locator(".generated-image-card");
        expect(await card.evaluate(el => {
            const probe = document.createElement("span");
            probe.style.backgroundColor = "var(--entry-surface)";
            el.appendChild(probe);
            const matches = getComputedStyle(el).backgroundColor === getComputedStyle(probe).backgroundColor;
            probe.remove();
            return matches;
        })).toBe(true);
    });
}

test("image controls fit phone screens and remain readable in every theme", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.route("**/images/generate", async route => {
        const request = route.request().postDataJSON();
        await route.fulfill({ status: 201, json: imagePayload(request.prompt, request.mode) });
    });

    await openMathTutor(page);
    await page.locator("#imageModeBtn").click();
    await page.locator("#userInput").fill("A simple illustration of the water cycle");
    await page.locator("#sendBtn").click();
    await expect(page.locator(".generated-image-card")).toBeVisible();

    for (const theme of ["light", "dark", "neon"]) {
        await page.locator("#aiSettingsBtn").click();
        await page.locator("#themeToggle").click();
        await page.locator(`[data-theme-choice="${theme}"]`).click();
        await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
        await page.keyboard.press("Escape");
        await expect(page.locator(".generated-image-action").first()).toBeVisible();
    }

    const box = await page.locator(".generated-image-card").boundingBox();
    const lastActionBox = await page.locator(".generated-image-action").last().boundingBox();
    const composerBox = await page.locator(".chat-input-area").boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(390);
    expect(lastActionBox.y + lastActionBox.height).toBeLessThanOrEqual(composerBox.y);
    await page.screenshot({ path: "/tmp/delphic-image-mobile-neon.png", fullPage: true });
});

test("HTML chat download embeds generated images and portable math", async ({ page }) => {
    const prompt = "Create a visual for x squared";
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "math-session", messages: [], images: [], tokens_used: 0,
    } }));
    await page.route("**/sessions", route => route.fulfill({
        status: 200,
        json: {
            current_session_id: "math-session",
            sessions: [{ session_id: "math-session", preview: "Quadratic visual" }],
        },
    }));
    await page.route("**/sessions/messages", route => route.fulfill({
        status: 200,
        json: {
            session_id: "math-session",
            tokens_used: 0,
            messages: [
                { id: 41, role: "user", content: prompt },
                { id: 42, role: "assistant", content: "This shows \\(x^2\\)." },
            ],
            images: [imagePayload(prompt).image],
        },
    }));

    await openMathTutor(page);
    await expect(page.locator("#currentSessionActionsBtn")).toBeVisible();
    await page.locator("#currentSessionActionsBtn").click();
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("menuitem", { name: "Download chat" }).click();
    const download = await downloadPromise;
    const path = await download.path();
    const html = fs.readFileSync(path, "utf8");

    expect(download.suggestedFilename()).toMatch(/\.html$/);
    expect(html).toContain("data:image/png;base64,");
    expect(html).toContain("AI-generated image");
    expect(html).toContain(prompt);
    expect(html).toContain("<math");
    expect(html).not.toContain("OPENROUTER_API_KEY");
});

test("large-export ZIP builder creates a standard ZIP directory", async ({ page }) => {
    await openMathTutor(page);
    const bytes = await page.evaluate(async () => {
        const archive = createZipBlob([
            { name: "delphic-chat.html", data: new TextEncoder().encode("<h1>Chat</h1>") },
            { name: "images/generated-image-1.png", data: new Uint8Array([1, 2, 3, 4]) },
        ]);
        return Array.from(new Uint8Array(await archive.arrayBuffer()));
    });
    expect(bytes.slice(0, 4)).toEqual([0x50, 0x4b, 0x03, 0x04]);
    expect(bytes.slice(-22, -18)).toEqual([0x50, 0x4b, 0x05, 0x06]);
});

test("large chat download produces a valid ZIP with HTML and image files", async ({ page }) => {
    const prompt = "A visual of a right triangle";
    await page.route("**/sessions/messages", route => route.fulfill({
        status: 200,
        json: {
            session_id: "math-session",
            tokens_used: 0,
            messages: [
                { id: 41, role: "user", content: prompt },
                { id: 42, role: "assistant", content: "Here is the image." },
            ],
            images: [imagePayload(prompt).image],
        },
    }));
    await openMathTutor(page);

    const downloadPromise = page.waitForEvent("download");
    await page.evaluate(() => downloadSessionChat({ session_id: "math-session" }, 0));
    const download = await downloadPromise;
    const path = await download.path();
    const listing = execFileSync("unzip", ["-Z1", path], { encoding: "utf8" });
    execFileSync("unzip", ["-t", path], { stdio: "pipe" });

    expect(download.suggestedFilename()).toMatch(/\.zip$/);
    expect(listing).toContain("delphic-chat.html");
    expect(listing).toContain("images/generated-image-1.png");
});
