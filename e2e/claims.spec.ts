import { expect, test, type APIRequestContext } from "@playwright/test";

async function post(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(path, { data });
  expect(response.ok()).toBe(true);
}

async function approve(
  request: APIRequestContext,
  claimId: string,
  payout: number,
) {
  await post(request, `/api/claims/${claimId}/start`, {});
  await post(request, `/api/claims/${claimId}/decision`, {
    decision: "approve",
    payout,
    reason: "The loss is covered by the policy wording.",
    policy_section: "5. Baggage and Personal Effects",
  });
}

test("the queue shows every claim", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Claims queue" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(25);
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
});

test("a claim shows the agent's steps as it works", async ({
  page,
  request,
}) => {
  await page.goto("/#/claims/CLM-1004");
  await expect(
    page.getByText("Checked bag arrived 31 hours late"),
  ).toBeVisible();
  await expect(
    page.getByText("The agent has not worked on this claim yet."),
  ).toBeVisible();

  await post(request, "/api/claims/CLM-1004/start", {});
  await post(request, "/api/claims/CLM-1004/steps", {
    kind: "tool_call",
    text: "get_claim({})",
  });
  await expect(page.getByText("get_claim({})")).toBeVisible();
  await expect(page.getByText("In progress").first()).toBeVisible();

  await post(request, "/api/claims/CLM-1004/decision", {
    decision: "refer",
    payout: 0,
    reason: "The delayed baggage report is missing.",
    policy_section: "4. Baggage Delay",
  });
  await post(request, "/api/claims/CLM-1004/steps", {
    kind: "reply",
    text: "Referred, no payout.",
  });
  const decision = page.getByRole("region", { name: "Decision" });
  await expect(
    decision.getByRole("heading", { name: "Referred" }),
  ).toBeVisible();
  await expect(
    decision.getByText("The delayed baggage report is missing."),
  ).toBeVisible();
  await expect(page.getByText("Referred, no payout.")).toBeVisible();
});

test("a payout over $1,000 waits for a handler's sign-off", async ({
  page,
  request,
}) => {
  await approve(request, "CLM-1002", 1100);
  const payment = await request.post("/api/claims/CLM-1002/payment", {
    data: { amount: 1100 },
  });
  expect(payment.status()).toBe(409);

  await page.goto("/#/claims/CLM-1002");
  await expect(page.getByText("Waiting for sign-off").first()).toBeVisible();
  await expect(page.getByText("Not paid yet")).toBeVisible();
  await page.getByRole("combobox").selectOption({ label: "Dana Whitfield" });
  await page
    .getByRole("button", { name: "Sign off and pay $1,100.00" })
    .click();
  await expect(
    page.getByText("Paid $1,100.00, signed off by Dana Whitfield"),
  ).toBeVisible();
  await expect(page.getByText("Decided").first()).toBeVisible();
});

test("a payout under $1,000 is paid without a sign-off", async ({
  page,
  request,
}) => {
  await approve(request, "CLM-1009", 450);
  await post(request, "/api/claims/CLM-1009/payment", { amount: 450 });
  await page.goto("/#/claims/CLM-1009");
  await expect(page.getByText("Paid $450.00")).toBeVisible();
  await expect(page.getByRole("region", { name: "Sign-off" })).toHaveCount(0);
});

test("the agent's instructions are read only", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Agent instructions" }).click();
  await expect(
    page.getByText("You are the UnderCover Agent.", { exact: false }),
  ).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});
