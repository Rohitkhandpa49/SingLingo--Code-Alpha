import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentProps } from "react";
import { describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "@/lib/api";
import { AuthForm } from "./auth-form";

const routerMocks = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));

vi.mock("next/link", () => ({
  default: ({ href, ...props }: ComponentProps<"a">) => <a href={href} {...props} />
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMocks
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, apiRequest: vi.fn() };
});

describe("registration form", () => {
  it("reports a password mismatch without sending credentials", async () => {
    const user = userEvent.setup();
    render(<AuthForm mode="register" />);

    await user.type(screen.getByLabelText("Full name"), "Asha Patel");
    await user.type(screen.getByLabelText("Email address"), "asha@example.com");
    await user.type(screen.getByLabelText("Password"), "password-one");
    await user.type(screen.getByLabelText("Confirm password"), "password-two");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByRole("alert")).toHaveTextContent("The passwords do not match.");
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
    expect(apiRequest).not.toHaveBeenCalled();
  });

  it("submits valid registration data and surfaces backend errors", async () => {
    vi.mocked(apiRequest).mockRejectedValueOnce(
      new ApiError(503, "Database is unavailable")
    );
    const user = userEvent.setup();
    render(<AuthForm mode="register" />);

    await user.type(screen.getByLabelText("Full name"), "Asha Patel");
    await user.type(screen.getByLabelText("Email address"), "asha@example.com");
    await user.type(screen.getByLabelText("Password"), "long-enough");
    await user.type(screen.getByLabelText("Confirm password"), "long-enough");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Database is unavailable");
    expect(apiRequest).toHaveBeenCalledWith(
      "/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          full_name: "Asha Patel",
          email: "asha@example.com",
          password: "long-enough",
          password_confirmation: "long-enough"
        })
      })
    );
    expect(routerMocks.push).not.toHaveBeenCalled();
  });
});

describe("password recovery form", () => {
  it("requests a reset email without disclosing whether the email is registered", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce({
      message: "If the account exists, password reset instructions will be emailed."
    });
    const user = userEvent.setup();
    render(<AuthForm mode="forgot-password" />);

    await user.type(screen.getByLabelText("Email address"), "asha@example.com");
    await user.click(screen.getByRole("button", { name: "Request reset link" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "If the account exists, password reset instructions will be emailed."
    );
    expect(apiRequest).toHaveBeenCalledWith(
      "/auth/password-reset/request",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "asha@example.com" })
      })
    );
  });
});
