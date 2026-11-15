const fs = require("fs");
const os = require("os");
const path = require("path");
const { defineConfig } = require("@playwright/test");

function findProjectPython() {
    const configuredPython = process.env.DELPHIC_PYTHON;
    const environmentPython = process.platform === "win32"
        ? ".venv/Scripts/python.exe"
        : ".venv/bin/python";
    const pythonPath = path.resolve(configuredPython || environmentPython);

    if (!fs.existsSync(pythonPath)) {
        throw new Error(
            `Delphic's Python was not found at ${pythonPath}. `
            + "Create .venv first, or set DELPHIC_PYTHON to the correct Python executable."
        );
    }

    return `"${pythonPath.replaceAll('"', '\\"')}"`;
}

const projectPython = findProjectPython();
const testPort = process.env.DELPHIC_TEST_PORT || "5004";
const testBaseUrl = `http://127.0.0.1:${testPort}`;
const testDataDir = process.env.DELPHIC_TEST_DATA_DIR
    || path.join(os.tmpdir(), `delphic-playwright-${process.pid}`);

module.exports = defineConfig({
    testDir: "./e2e",
    // Graph rendering and session tests share one local Flask development server.
    // Running them in sequence keeps the check stable on school laptops.
    workers: 1,
    timeout: 30_000,
    use: {
        baseURL: testBaseUrl,
        screenshot: "only-on-failure",
        trace: "retain-on-failure",
    },
    webServer: {
        command: `${projectPython} app.py`,
        cwd: process.env.DELPHIC_TEST_APP_ROOT || __dirname,
        url: `${testBaseUrl}/`,
        env: {
            ...process.env,
            PORT: testPort,
            // Test image UI with mocked providers, never student or paid requests.
            DELPHIC_ENABLE_EXPERIMENTAL_IMAGES: "true",
            DELPHIC_DATA_DIR: testDataDir,
            FLASK_SECRET_KEY: "playwright-test-only-secret",
        },
        reuseExistingServer: false,
        stdout: "ignore",
        stderr: "ignore",
        timeout: 30_000,
    },
});
