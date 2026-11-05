import { test, expect } from "@playwright/test";
import { login } from "./helpers";

test.describe("navigation & theme", () => {
  test("sidebar navigates to feature pages", async ({ page }) => {
    await login(page);
    await page.getByRole("link", { name: "Vulnerability Analysis" }).click();
    await expect(page).toHaveURL(/\/vulnerability-analysis/);
    await expect(page.getByRole("heading", { name: /vulnerability analysis/i })).toBeVisible();

    await page.getByRole("link", { name: "Phishing Analysis" }).click();
    await expect(page).toHaveURL(/\/phishing-analysis/);

    await page.getByRole("link", { name: "Runs" }).click();
    await expect(page).toHaveURL(/\/runs/);
  });

  test("theme toggle switches between light and dark", async ({ page }) => {
    await login(page);
    const html = page.locator("html");
    const before = await html.getAttribute("class");
    await page.getByRole("button", { name: "Toggle theme" }).click();
    await expect(html).not.toHaveClass(before ?? "");
  });
});
