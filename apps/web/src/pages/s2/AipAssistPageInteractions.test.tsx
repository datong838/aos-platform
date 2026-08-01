import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

vi.mock("../../api/client", () => ({
  apiGet: mocks.apiGet,
  apiPost: mocks.apiPost,
}));

vi.mock("../../api/apiBase", () => ({
  getApiBase: () => "http://127.0.0.1:8080",
}));

import { AipAssistPage } from "./AipAssistPage";

async function flushEffects() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await Promise.resolve();
  });
}

describe("AIP Assist suggestion contract", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("renders real object suggestions and fills the input when clicked", async () => {
    mocks.apiGet.mockResolvedValue({
      items: [
        { id: "sg-001", category: "data", text: "今天有哪些数据流出现了延迟？" },
        { id: "sg-002", category: "data", text: "今天有哪些数据流出现了延迟？" },
        { id: "sg-003", category: "build", text: "查看最近构建日志" },
      ],
    });

    await act(async () => {
      root.render(
        <MemoryRouter>
          <AipAssistPage />
        </MemoryRouter>,
      );
    });
    await flushEffects();

    const matchingButtons = Array.from(host.querySelectorAll("button")).filter(
      (button) => button.textContent?.includes("今天有哪些数据流出现了延迟？"),
    );
    expect(matchingButtons).toHaveLength(1);

    await act(async () => matchingButtons[0].click());
    const input = host.querySelector('input[placeholder="提出问题..."]') as HTMLInputElement;
    expect(input.value).toBe("今天有哪些数据流出现了延迟？");
  });
});
