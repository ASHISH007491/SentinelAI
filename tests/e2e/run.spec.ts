import { test, expect } from "@playwright/test";
import { login } from "./helpers";

/**
 * Full end-to-end run. Requires the BACKEND to be running so the upload triggers
 * a real create -> upload -> execute and findings render.
 */
test.describe("vulnerability run", () => {
  test("uploading a file produces agent findings", async ({ page }) => {
    await login(page);
    await page.goto("/vulnerability-analysis");

    // A file with obvious issues so the rule-based detector returns findings.
    const content = [
      "import os",
      "def run(cmd):",
      "    os.system(cmd)  # command injection",
      "app.run(debug=True)",
    ].join("\n");

    await page.locator('input[type="file"]').setInputFiles({
      name: "vulnerable.py",
      mimeType: "text/x-python",
      buffer: Buffer.from(content),
    });

    // Agent results / live badge should appear once the run completes.
    await expect(page.getByText(/analysis complete|live/i).first()).toBeVisible({ timeout: 20_000 });
  });
});
