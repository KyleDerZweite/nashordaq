import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

function portfolio(page: Page) {
  return page.getByRole("button", { name: "Open portfolio insights" });
}

function cash(page: Page) {
  return portfolio(page)
    .getByText("Poros", { exact: true })
    .locator("..")
    .locator("span")
    .last();
}

async function expectEmptyPortfolio(page: Page) {
  await expect(portfolio(page)).toBeVisible();
  await expect(cash(page)).toHaveText("1.000,00");
  await expect(portfolio(page).locator("tbody tr")).toHaveCount(0);
}

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("demo");
  await page.getByLabel("Password", { exact: true }).fill("demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByText("Demo trades use your own temporary portfolio.", {
      exact: false,
    }),
  ).toBeVisible();
  await expectEmptyPortfolio(page);
}

test("demo visitors keep separate portfolios across trade, reload and logout", async ({
  browser,
  playwright,
  baseURL,
}, testInfo) => {
  const first = await browser.newContext({ baseURL });
  const second = await browser.newContext({ baseURL });
  const a = await first.newPage();
  const b = await second.newPage();
  try {
    await test.step("Two visitors sign in with fresh personal state", async () => {
      await signIn(a);
      await signIn(b);
    });

    let stock = "";
    let balanceAfterBuy = "";
    await test.step("A buys one rendered stock while B stays unchanged", async () => {
      const card = a
        .getByRole("article")
        .filter({ has: a.getByRole("button", { name: "Buy", exact: true }) })
        .first();
      await expect(card.getByRole("heading")).toBeVisible();
      stock = (await card.getByRole("heading").innerText()).trim();
      await card.getByRole("button", { name: "Buy", exact: true }).click();
      const ticket = a.locator("section").filter({
        has: a.getByRole("heading", { name: `BUY: ${stock}`, exact: true }),
      });
      await expect(ticket.getByRole("spinbutton")).toHaveValue("1");
      await ticket
        .getByRole("button", { name: "BUY 1 share", exact: true })
        .click();
      const holding = portfolio(a).getByRole("row").filter({ hasText: stock });
      await expect(holding.getByRole("cell").nth(1)).toHaveText("1");
      await expect(cash(a)).not.toHaveText("1.000,00");
      balanceAfterBuy = (await cash(a).innerText()).trim();
      expect(
        Number(balanceAfterBuy.replaceAll(".", "").replace(",", ".")),
      ).toBeLessThan(1000);
      await b.reload();
      await expectEmptyPortfolio(b);
    });

    await test.step("Reload preserves A's session and holding", async () => {
      await a.reload();
      const holding = portfolio(a).getByRole("row").filter({ hasText: stock });
      await expect(holding.getByRole("cell").nth(1)).toHaveText("1");
      await expect(cash(a)).toHaveText(balanceAfterBuy);
    });

    await test.step("A signs out and its old cookie loses access", async () => {
      const cookie = (await first.cookies()).find(
        (entry) => entry.name === "nashordaq_session",
      );
      expect(Boolean(cookie), "A has a session cookie before logout").toBe(
        true,
      );
      if (!cookie) throw new Error("A has no session cookie before logout.");
      await a.getByRole("button", { name: "Account menu" }).click();
      await a.getByRole("button", { name: "Sign out", exact: true }).click();
      await expect(a.getByLabel("Username", { exact: true })).toBeVisible();
      await expect(portfolio(a)).toHaveCount(0);
      const replay = await playwright.request.newContext({
        baseURL,
        extraHTTPHeaders: { Cookie: `${cookie.name}=${cookie.value}` },
      });
      try {
        // Do not expose a cookie-bearing Playwright request log on transport failure.
        const response = await replay.get("/api/auth/session").catch(() => {
          throw new Error(
            "Revoked-cookie request did not return an HTTP response.",
          );
        });
        expect(response.status()).toBe(401);
      } finally {
        await replay.dispose();
      }
    });

    await test.step("B retains its independent session after A signs out", async () => {
      await b.reload();
      await expectEmptyPortfolio(b);
      await expect(
        b.getByRole("button", { name: "Account menu" }),
      ).toBeVisible();
    });
  } catch (error) {
    await Promise.allSettled([
      a.screenshot({
        path: testInfo.outputPath("visitor-a.png"),
        fullPage: true,
      }),
      b.screenshot({
        path: testInfo.outputPath("visitor-b.png"),
        fullPage: true,
      }),
    ]);
    throw error;
  } finally {
    await first.close();
    await second.close();
  }
});
