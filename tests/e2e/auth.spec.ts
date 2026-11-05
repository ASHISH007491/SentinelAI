import { test, expect } from "@playwright/test";
import { login, SEED } from "./helpers";

test.describe("authentication", () => {
  test("unauthenticated user is redirected to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("seeded admin can log in and reach the dashboard", async ({ page }) => {
    await login(page);
    await expect(page.getByRole("heading", { name: /security dashboard/i })).toBeVisible();
  });

  test("logout returns to the login page", async ({ page }) => {
    await login(page);
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: /log out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("registration page validates and links back to login", async ({ page }) => {
    await page.goto("/register");
    await page.getByRole("button", { name: "Create account" }).click();
    // Zod validation should surface inline errors, keeping us on /register.
    await expect(page).toHaveURL(/\/register/);
    await page.getByRole("link", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
