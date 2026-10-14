from pathlib import Path
p=Path('apps/web/src/components/workshop/CreatorGrowthPage.test.tsx');s=p.read_text();pos=s.rfind('\n});');assert pos>0
s=s[:pos]+'''

  const openPreparation = () => act(async () => { window.dispatchEvent(new CustomEvent("aos-workshop-creator-import")); });
  const reloadDrafts = () => act(async () => { host.querySelector<HTMLButtonElement>(".creator-growth-analysis footer button")!.click(); });
  const editField = async (selector: string, value: string, kind: "input" | "textarea" = "input") => {
    const element = host.querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
    await act(async () => { Object.getOwnPropertyDescriptor(kind === "input" ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype, "value")!.set!.call(element, value); element.dispatchEvent(new Event("input", { bubbles: true })); });
  };
  const commandButtons = () => [...host.querySelectorAll<HTMLButtonElement>(".creator-growth-preparation-actions button, .creator-growth-workflow-history button")];

  it("首次草稿读取失败明确禁入，不冒充成功空列表", async () => {
    const client = clientFor(); client.listCreatorInternalWorkflows.mockRejectedValueOnce(new Error("private error"));
    await act(async () => root.render(<CreatorGrowthPage client={client} />)); await openPreparation();
    await editField('textarea[aria-label="来源与筛选条件"]', "我正在整理的候选条件", "textarea");
    const save = commandButtons().find((b) => b.textContent === "保存草稿")!;
    expect(save.disabled).toBe(true); expect(host.textContent).toContain("当前内部草稿暂未读取");
    expect(host.textContent).not.toContain("private error");
    await act(async () => save.click()); expect(client.executeCreatorInternalWorkflow).not.toHaveBeenCalled();
  });

  it("合法空列表保留既有准备入口", async () => {
    const client = clientFor(); await act(async () => root.render(<CreatorGrowthPage client={client} />)); await openPreparation();
    await editField('textarea[aria-label="来源与筛选条件"]', "合法的内部准备内容", "textarea");
    expect(commandButtons().find((b) => b.textContent === "保存草稿")!.disabled).toBe(false);
    expect(host.textContent).not.toContain("当前内部草稿暂未读取");
  });

  it("刷新中及失败后缓存不是当前权威，保留编辑并禁审核恢复", async () => {
    const client = clientFor(); const review = { ...draft, revision: 2, version: 2, status: "in_review" as const };
    let rejectRead!: (reason: Error) => void;
    client.listCreatorInternalWorkflows.mockResolvedValueOnce({ tenant: emptyView.tenant, items: [review], count: 1 })
      .mockImplementationOnce(() => new Promise((_, reject) => { rejectRead = reject; }))
      .mockResolvedValueOnce({ tenant: emptyView.tenant, items: [review], count: 1 });
    await act(async () => root.render(<CreatorGrowthPage client={client} />)); await openPreparation();
    await editField('input[aria-label="任务名称"]', "尚未保存的编辑名称");
    await reloadDrafts(); expect(commandButtons().length).toBeGreaterThan(2);
    for (const button of commandButtons()) expect(button.disabled).toBe(true);
    await act(async () => rejectRead(new Error("unknown saved state")));
    expect(host.textContent).toContain("上次读取：审核中"); expect(host.querySelector('[aria-label="当前草稿"]')).toBeNull();
    expect(host.querySelector<HTMLInputElement>('input[aria-label="任务名称"]')!.value).toBe("尚未保存的编辑名称");
    for (const button of commandButtons()) { expect(button.disabled).toBe(true); await act(async () => button.click()); }
    expect(client.executeCreatorInternalWorkflow).not.toHaveBeenCalled();
    await reloadDrafts(); expect(host.querySelector('[aria-label="当前草稿"]')).not.toBeNull();
    expect(host.querySelector<HTMLInputElement>('input[aria-label="任务名称"]')!.value).toBe("尚未保存的编辑名称");
    expect(commandButtons().find((b) => b.textContent === "批准")!.disabled).toBe(false);
    expect(client.executeCreatorInternalWorkflow).not.toHaveBeenCalled();
  });

  it("旧读取迟到失败不能覆盖新的成功快照", async () => {
    const client = clientFor(); let rejectOld!: (reason: Error) => void;
    client.listCreatorInternalWorkflows.mockResolvedValueOnce({ tenant: emptyView.tenant, items: [draft], count: 1 })
      .mockImplementationOnce(() => new Promise((_, reject) => { rejectOld = reject; }))
      .mockResolvedValueOnce({ tenant: emptyView.tenant, items: [draft], count: 1 });
    await act(async () => root.render(<CreatorGrowthPage client={client} />)); await openPreparation();
    await reloadDrafts(); await reloadDrafts(); await act(async () => rejectOld(new Error("stale error")));
    expect(host.textContent).not.toContain("当前内部草稿暂未读取"); expect(host.querySelector('[aria-label="当前草稿"]')).not.toBeNull();
    expect(client.executeCreatorInternalWorkflow).not.toHaveBeenCalled();
  });

  it("读取失败不删除已成功回执或自动重发", async () => {
    const client = clientFor(); await act(async () => root.render(<CreatorGrowthPage client={client} />)); await openPreparation();
    await editField('textarea[aria-label="来源与筛选条件"]', "既有内部准备测试内容", "textarea");
    await act(async () => commandButtons().find((b) => b.textContent === "保存草稿")!.click());
    expect(client.executeCreatorInternalWorkflow).toHaveBeenCalledTimes(1);
    client.listCreatorInternalWorkflows.mockRejectedValueOnce(new Error("read unavailable")); await reloadDrafts();
    expect(host.textContent).toContain("回执 receipt-1"); expect(host.textContent).toContain("上次读取：草稿");
    expect(client.executeCreatorInternalWorkflow).toHaveBeenCalledTimes(1);
  });
''' +s[pos:];p.write_text(s)
