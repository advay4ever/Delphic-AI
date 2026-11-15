const { test, expect } = require("@playwright/test");

const colors = [
    ["cyan", "Cyan", "#00FFFF"], ["electric-blue", "Electric blue", "#00BFFF"],
    ["mint", "Mint", "#00FFA3"], ["green", "Green", "#39FF14"],
    ["yellow", "Yellow", "#FFFF33"], ["orange", "Orange", "#FF5F1F"],
    ["pink", "Pink", "#FF10F0"], ["purple", "Purple", "#BC13FE"],
];
const storageKey = "delphic-neon-accent";

async function mockWorkspace(page, configured = true) {
    await page.route("**/ai-settings", route => route.fulfill({ json: {
        configured, provider: "groq", model: "test", can_forget: configured,
        providers: [{ id: "groq", label: "Groq", models: [{ id: "test", label: "Test" }] }],
    } }));
    await page.route("**/history", route => route.fulfill({ json: {
        session_id: "neon-test", messages: [], images: [], tokens_used: 7,
    } }));
    await page.route("**/sessions", route => route.fulfill({ json: {
        current_session_id: "neon-test", sessions: [],
    } }));
    await page.route("**/library/status?*", route => route.fulfill({ json: { enabled_count: 0 } }));
}

async function changeTheme(page, theme) {
    await page.locator("#themeToggle").click();
    await page.locator(`[data-theme-choice="${theme}"]`).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
}

function rgb(hex) {
    return `rgb(${[1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)).join(", ")})`;
}

async function readable(locator, surfaceToken) {
    const contrast = await locator.evaluate((el, token) => {
        const canvas = document.createElement("canvas");
        canvas.width = canvas.height = 1;
        const context = canvas.getContext("2d");
        const parse = color => {
            context.clearRect(0, 0, 1, 1);
            context.fillStyle = color;
            context.fillRect(0, 0, 1, 1);
            const pixel = [...context.getImageData(0, 0, 1, 1).data];
            return [...pixel.slice(0, 3), pixel[3] / 255];
        };
        const style = getComputedStyle(el);
        const surface = parse(style.getPropertyValue(token));
        const fill = parse(style.backgroundColor);
        const background = surface.map((v, i) => v * (1 - fill[3]) + fill[i] * fill[3]);
        const luminance = values => values.slice(0, 3).map(v => {
            const s = v / 255;
            return s <= .04045 ? s / 12.92 : ((s + .055) / 1.055) ** 2.4;
        }).reduce((sum, v, i) => sum + v * [.2126, .7152, .0722][i], 0);
        const a = luminance(parse(style.color)), b = luminance(background);
        return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    }, surfaceToken);
    expect(contrast, await locator.getAttribute("class")).toBeGreaterThanOrEqual(4.5);
}

for (const mode of ["math", "science"]) {
    test(`${mode} all eight Neon accents fit and remain readable on desktop and mobile`, async ({ page }, testInfo) => {
        test.setTimeout(60_000);
        const errors = [], mutations = [];
        page.on("pageerror", error => errors.push(error.message));
        page.on("request", request => { if (request.method() !== "GET") mutations.push(request.url()); });
        await mockWorkspace(page);
        await page.emulateMedia({ reducedMotion: "reduce" });
        await page.addInitScript(() => localStorage.setItem("math-tutor-theme", "neon"));
        for (const viewport of [
            { width: 1440, height: 900 }, { width: 768, height: 1024 },
            { width: 390, height: 844 }, { width: 320, height: 480 },
            { width: 640, height: 360 },
        ]) {
            await page.setViewportSize(viewport);
            await page.goto(mode === "science" ? "/science" : "/#tutor");
            if (!await page.locator("#stepByStepToggle").isChecked()) {
                await page.locator("#stepByStepToggle").focus();
                await page.keyboard.press("Space");
            }
            await page.locator("#aiSettingsBtn").click();
            await expect(page.getByRole("radio")).toHaveCount(8);
            await page.getByRole("radio", { name: "Purple", exact: true }).check();
            for (const [id, label, hex] of colors) {
                const option = page.getByRole("radio", { name: label, exact: true });
                await option.check();
                await expect(option).toBeChecked();
                await expect(page.locator("#neonAccentName")).toHaveText(label);
                await expect(page.locator("html")).toHaveAttribute("data-neon-accent", id);
                expect(await page.evaluate(key => localStorage.getItem(key), storageKey)).toBe(id);
                await expect(page.locator("#sendBtn")).toHaveCSS("background-color", rgb(hex));
                await expect(page.locator(".toggle-thumb")).toHaveCSS("background-color", "rgb(16, 35, 38)");
                const box = await option.boundingBox();
                expect(box.width).toBeGreaterThanOrEqual(44);
                expect(box.height).toBe(44);
                expect(box.x).toBeGreaterThanOrEqual(0);
                expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
                expect(box.y).toBeGreaterThanOrEqual(0);
                expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
                await expect(option.locator("+ .neon-accent-swatch svg")).toBeVisible();
                expect(await page.locator(".ai-settings-panel").evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
                for (const [selector, surface] of [
                    [".workspace-switch.is-current", "--sidebar-surface"],
                    ["#sendBtn", "--entry-surface"], ["#neonAccentName", "--tool-surface"],
                    [".new-chat-btn", "--sidebar-surface"],
                    ["#aiSettingsSubmitBtn", "--tool-surface"], [".theme-option.is-selected", "--tool-surface"],
                ]) await readable(page.locator(selector), surface);
            }
            await page.locator(".ai-settings-close").click({ trial: true });
            await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-purple-settings.png`) });
            await page.keyboard.press("Escape");
            await page.locator("#sendBtn").scrollIntoViewIfNeeded();
            await page.screenshot({ path: testInfo.outputPath(`${mode}-${viewport.width}-purple-workspace.png`) });
            expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
        }
        expect(errors).toEqual([]);
        expect(mutations).toEqual([]);
    });

    test(`${mode} keyboard selection saves across reload, Home, and both tutors`, async ({ page }) => {
        await mockWorkspace(page);
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.locator("#aiSettingsBtn").click();
        await expect(page.locator("#neonAccentControls")).toBeHidden();
        await changeTheme(page, "neon");
        const cyan = page.getByRole("radio", { name: "Cyan", exact: true });
        await expect(cyan).toBeChecked();
        await page.keyboard.press("Tab");
        await expect(cyan).toBeFocused();
        await expect(cyan.locator("+ .neon-accent-swatch")).toHaveCSS("outline-style", "solid");
        await page.keyboard.press("ArrowRight");
        await expect(page.getByRole("radio", { name: "Electric blue", exact: true })).toBeChecked();
        await page.keyboard.press("ArrowLeft");
        await expect(cyan).toBeChecked();
        await page.keyboard.press("ArrowLeft");
        await expect(page.getByRole("radio", { name: "Purple", exact: true })).toBeChecked();
        await page.keyboard.press("Escape");
        for (const url of ["/", "/#tutor", "/science"]) {
            await page.goto(url);
            await expect(page.locator("html")).toHaveAttribute("data-neon-accent", "purple");
            await expect(page.locator("html")).toHaveAttribute("data-theme", "neon");
            if (url === "/") {
                for (const button of await page.locator(".home-actions button").all()) await readable(button, "--home-canvas");
            } else await expect(page.locator("#sendBtn")).toHaveCSS("background-color", rgb("#BC13FE"));
            await page.reload();
            await expect(page.locator("html")).toHaveAttribute("data-neon-accent", "purple");
        }
    });
}

test("Accent synchronizes across tabs without changing the other tab's theme", async ({ context, page }) => {
    await mockWorkspace(page);
    await page.goto("/#tutor");
    await page.locator("#aiSettingsBtn").click();
    await changeTheme(page, "neon");
    const other = await context.newPage();
    await mockWorkspace(other);
    await other.goto("/science");
    await other.locator("#aiSettingsBtn").click();
    await page.getByRole("radio", { name: "Mint", exact: true }).check();
    await expect(other.getByRole("radio", { name: "Mint", exact: true })).toBeChecked();
    await changeTheme(other, "dark");
    await page.getByRole("radio", { name: "Orange", exact: true }).check();
    await expect(other.locator("html")).toHaveAttribute("data-neon-accent", "orange");
    await expect(other.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(other.locator("#neonAccentControls")).toBeHidden();
    await page.evaluate(key => localStorage.removeItem(key), storageKey);
    await expect(other.locator("html")).toHaveAttribute("data-neon-accent", "cyan");
});

for (const mode of ["math", "science"]) {
test(`${mode} saved accent cannot change Light or Dark surfaces, text, or controls`, async ({ page }) => {
    await mockWorkspace(page);
    await page.goto(mode === "science" ? "/science" : "/#tutor");
    await page.emulateMedia({ reducedMotion: "reduce" });
    const snapshot = () => page.locator("#sendBtn, .text-pill, .workspace-switch.is-current, .ai-settings-panel, .ai-settings-message").evaluateAll(elements => elements.map(el => {
        const s = getComputedStyle(el);
        return [s.color, s.backgroundColor, s.borderColor, s.boxShadow];
    }));
    await page.locator("#aiSettingsBtn").click();
    for (const theme of ["light", "dark"]) {
        await changeTheme(page, theme);
        await expect(page.locator(".text-pill")).toHaveCSS("background-color", theme === "light" ? "rgba(255, 255, 255, 0.88)" : "rgba(36, 43, 47, 0.9)");
        await expect(page.locator(".text-pill")).toHaveCSS("color", theme === "light" ? "rgb(26, 26, 46)" : "rgb(226, 232, 240)");
        await page.evaluate(() => {
            const message = document.getElementById("aiSettingsMessage");
            message.textContent = "Test error"; message.classList.add("is-error"); message.hidden = false;
        });
        const before = await snapshot();
        await page.evaluate(key => {
            localStorage.setItem(key, "purple");
            window.dispatchEvent(new StorageEvent("storage", { key, newValue: "purple" }));
        }, storageKey);
        expect(await snapshot()).toEqual(before);
        await expect(page.locator("#neonAccentControls")).toBeHidden();
        await page.evaluate(key => {
            localStorage.removeItem(key);
            window.dispatchEvent(new StorageEvent("storage", { key, newValue: null }));
        }, storageKey);
    }
});
}

for (const mode of ["math", "science"]) {
    test(`${mode} Neon changes real surface fills and glow, not just borders`, async ({ page }, testInfo) => {
        await mockWorkspace(page);
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto(mode === "science" ? "/science" : "/#tutor");
        await page.locator("#aiSettingsBtn").click();
        const selectors = [".chat-workspace", ".sidebar", ".chat-header", ".text-pill", ".new-chat-btn", ".starter-prompts button", ".ai-settings-panel"];
        const surfaces = async () => {
            const fills = [];
            for (const selector of selectors) fills.push(await page.locator(selector).first().evaluate(el => {
                const style = getComputedStyle(el);
                return [style.backgroundColor, style.backgroundImage];
            }));
            return fills;
        };
        const dark = await surfaces();
        await changeTheme(page, "neon");
        const palettes = new Set();
        for (const [id, label, hex] of colors) {
            await page.getByRole("radio", { name: label, exact: true }).check();
            const expectedFill = await page.locator(".text-pill").evaluate(el => {
                const probe = document.createElement("span");
                probe.style.backgroundColor = "var(--entry-glass)";
                el.append(probe);
                const color = getComputedStyle(probe).backgroundColor;
                probe.remove();
                return color;
            });
            await expect(page.locator(".text-pill")).toHaveCSS("background-color", expectedFill);
            await expect(page.locator(".new-chat-btn")).toHaveCSS("background-color", rgb(hex));
            const neon = await surfaces();
            for (let i = 0; i < selectors.length; i++) expect(neon[i], selectors[i]).not.toEqual(dark[i]);
            palettes.add(JSON.stringify(neon));
            for (const selector of [".text-pill", "#sendBtn", ".new-chat-btn"]) {
                await expect(page.locator(selector)).not.toHaveCSS("box-shadow", "none");
            }
            for (const selector of ["#userInput", ".step-toggle", ".starter-prompts button"]) await readable(page.locator(selector).first(), "--entry-surface");
            await page.keyboard.press("Escape");
            await page.mouse.move(0, 0);
            await page.screenshot({ path: testInfo.outputPath(`${mode}-${id}-neon-surfaces.png`) });
            await page.locator("#aiSettingsBtn").click();
        }
        expect(palettes.size).toBe(8);
    });
}

test("Home uses the selected Neon canvas and filled tutor buttons without changing Dark", async ({ page }) => {
    await mockWorkspace(page);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    const home = page.locator("#homePage");
    const dark = await home.evaluate(el => getComputedStyle(el).backgroundColor);
    await page.evaluate(() => document.documentElement.dataset.theme = "neon");
    const surfaces = new Set();
    for (const [id, , hex] of colors) {
        await page.evaluate(({ key, id }) => {
            localStorage.setItem(key, id);
            window.dispatchEvent(new StorageEvent("storage", { key, newValue: id }));
        }, { key: storageKey, id });
        const surface = await home.evaluate(el => getComputedStyle(el).backgroundColor);
        expect(surface).not.toBe(dark);
        surfaces.add(surface);
        for (const button of await page.locator(".home-actions button").all()) {
            await expect(button).toHaveCSS("background-color", rgb(hex));
            await readable(button, "--home-canvas");
        }
        await readable(page.locator(".home-tagline"), "--home-canvas");
    }
    expect(surfaces.size).toBe(8);
    await page.evaluate(() => document.documentElement.dataset.theme = "dark");
    await expect(home).toHaveCSS("background-color", dark);
});

for (const invalid of ["not-a-color", "url(https://invalid.example/track)"]) {
    test(`Invalid saved accent falls back safely: ${invalid}`, async ({ page }) => {
        await mockWorkspace(page);
        const requests = [];
        page.on("request", request => { if (request.url().includes("invalid.example")) requests.push(request.url()); });
        await page.addInitScript(({ key, value }) => {
            localStorage.setItem("math-tutor-theme", "neon"); localStorage.setItem(key, value);
        }, { key: storageKey, value: invalid });
        await page.goto("/#tutor");
        await expect(page.locator("html")).toHaveAttribute("data-neon-accent", "cyan");
        await expect(page.locator("#sendBtn")).toHaveCSS("background-color", rgb("#00FFFF"));
        await page.locator("#aiSettingsBtn").click();
        await expect(page.getByRole("radio", { name: "Cyan", exact: true })).toBeChecked();
        expect(requests).toEqual([]);
    });
}

test("Blocked accent storage keeps the page usable and selection lasts for the page", async ({ page }) => {
    await mockWorkspace(page);
    await page.addInitScript(key => {
        localStorage.setItem("math-tutor-theme", "neon");
        for (const method of ["getItem", "setItem"]) {
            const original = Storage.prototype[method];
            Storage.prototype[method] = function (...args) {
                if (args[0] === key) throw new DOMException("Blocked", "SecurityError");
                return original.apply(this, args);
            };
        }
    }, storageKey);
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto("/#tutor");
    await page.locator("#aiSettingsBtn").click();
    await page.getByRole("radio", { name: "Pink", exact: true }).check();
    await expect(page.locator("html")).toHaveAttribute("data-neon-accent", "pink");
    await changeTheme(page, "dark");
    await changeTheme(page, "neon");
    await expect(page.getByRole("radio", { name: "Pink", exact: true })).toBeChecked();
    expect(errors).toEqual([]);
});

test("Accent changes preserve the connection draft and semantic error color", async ({ page }) => {
    await mockWorkspace(page, false);
    const mutations = [];
    page.on("request", request => { if (request.method() !== "GET") mutations.push(request.url()); });
    await page.goto("/#tutor");
    await page.locator("#aiSettingsBtn").click();
    await page.locator("#aiApiKeyInput").fill("not-a-real-key-unsaved-draft");
    await changeTheme(page, "neon");
    await page.evaluate(() => {
        const message = document.getElementById("aiSettingsMessage");
        message.textContent = "Test error"; message.classList.add("is-error"); message.hidden = false;
    });
    const errorColor = await page.locator("#aiSettingsMessage").evaluate(el => getComputedStyle(el).color);
    for (const [, label] of colors) {
        await page.getByRole("radio", { name: label, exact: true }).check();
        await expect(page.locator("#aiApiKeyInput")).toHaveValue("not-a-real-key-unsaved-draft");
        await expect(page.locator("#aiSettingsMessage")).toHaveCSS("color", errorColor);
    }
    expect(mutations).toEqual([]);
});
