import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearAccessToken, setAccessToken } from "../../api/tenant";
import { DevOidcSessionBanner } from "./DevOidcSessionBanner";

const loginPassword = vi.hoisted(() => vi.fn());
vi.mock("../../api/passwordLogin", () => ({ loginPassword }));

let host: HTMLDivElement;
let root: Root;

async function renderBanner() {
  await act(async () => root.render(<DevOidcSessionBanner />));
}

async function setInput(label: string, value: string) {
  const input = Array.from(host.querySelectorAll("label")).find((item) => item.textContent?.startsWith(label))
    ?.querySelector("input") as HTMLInputElement | undefined;
  if (!input) throw new Error(`missing ${label}`);
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  return input;
}

beforeEach(() => {
  vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  clearAccessToken();
  loginPassword.mockReset();
  host = document.createElement("div");
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  clearAccessToken();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("development optional OIDC login", () => {
  it("keeps login optional until the human explicitly opens it", async () => {
    await renderBanner();
    expect(host.textContent).toContain("开发模式");
    expect(host.querySelector('input[type="password"]')).toBeNull();
    expect(loginPassword).not.toHaveBeenCalled();

    await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
    expect(host.querySelector('input[type="password"]')).not.toBeNull();
    expect(loginPassword).not.toHaveBeenCalled();
  });

  it("reuses the human login path once and closes after a verified session", async () => {
    loginPassword.mockImplementation(async () => setAccessToken("verified-oidc"));
    await renderBanner();
    await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
    await setInput("登录名", "human-maker");
    await setInput("密码", "private-value");
    await act(async () => host.querySelector<HTMLFormElement>("form")!.requestSubmit());

    expect(loginPassword).toHaveBeenCalledTimes(1);
    expect(loginPassword).toHaveBeenCalledWith("human-maker", "private-value");
    expect(host.querySelector('input[type="password"]')).toBeNull();
    expect(host.textContent).toBe("");
  });

  it("does not retry a failed login and clears the password field", async () => {
    loginPassword.mockRejectedValue(new Error("登录失败，请核对账号、密码及工作区访问权限后重试。"));
    await renderBanner();
    await act(async () => host.querySelector<HTMLButtonElement>("button")!.click());
    await setInput("登录名", "human-maker");
    const password = await setInput("密码", "wrong-value");
    await act(async () => host.querySelector<HTMLFormElement>("form")!.requestSubmit());

    expect(loginPassword).toHaveBeenCalledTimes(1);
    expect(password.value).toBe("");
    expect(host.textContent).toContain("登录失败");
  });

  it("stays hidden outside bypass mode or when a session already exists", async () => {
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "0");
    await renderBanner();
    expect(host.textContent).toBe("");

    await act(async () => root.unmount());
    root = createRoot(host);
    vi.stubEnv("VITE_AOS_SKIP_LOGIN_GATE", "1");
    setAccessToken("verified-oidc");
    await renderBanner();
    expect(host.textContent).toBe("");
  });
});
