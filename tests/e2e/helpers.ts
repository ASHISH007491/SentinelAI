import { type Page, expect } from "@playwright/test";

export const SEED = { email: "admin@sentinelai.app", password: "admin12345" };

/** Log in via the UI using the seeded admin account. */
export async function login(page: Page, email = SEED.email, password = SEED.password) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}
