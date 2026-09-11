// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
const send = vi.hoisted(() => vi.fn());
const actor = vi.hoisted(() => ({orgId:'org-org'}));
vi.mock('./client', () => ({ apiPostImmediate: send }));
vi.mock('./tenant', () => ({ getTenant: () => ({orgId:actor.orgId,projectId:'dev-project',subject:'user'}) }));
import { recoverScheduledRun } from './scheduleRecovery';

beforeEach(() => { sessionStorage.clear(); send.mockReset(); actor.orgId='org-org'; });
describe('recovery request identity', () => {
  it('does not share claims across tenants', async () => {
    send.mockResolvedValue({status:'duplicate'});
    await recoverScheduledRun('s','r','at1');
    actor.orgId='dev-org';
    await recoverScheduledRun('s','r','at1');
    expect(send.mock.calls[0][1]).not.toEqual(send.mock.calls[1][1]);
  });
  it('does not clear a newer request when an older response arrives', async () => {
    let finish!: (value: {status:string}) => void;
    send.mockImplementationOnce(() => new Promise(resolve => { finish=resolve; })).mockResolvedValue({status:'duplicate'});
    const old=recoverScheduledRun('s','r','at1');
    await recoverScheduledRun('s','r','at2');
    finish({status:'failed'}); await old;
    await recoverScheduledRun('s','r','at2');
    expect(send.mock.calls[1][1]).toEqual(send.mock.calls[2][1]);
  });
  it('reuses the claim after an unknown result', async () => {
    send.mockRejectedValue(new Error('network'));
    await expect(recoverScheduledRun('s','r','at1')).rejects.toThrow('network');
    await expect(recoverScheduledRun('s','r','at1')).rejects.toThrow('network');
    expect(send.mock.calls[0][1]).toEqual(send.mock.calls[1][1]);
  });
  it('keeps duplicate identity and rotates after confirmed completion', async () => {
    send.mockResolvedValueOnce({status:'duplicate'}).mockResolvedValueOnce({status:'failed'}).mockResolvedValueOnce({status:'succeeded'});
    await recoverScheduledRun('s','r','at1');
    await recoverScheduledRun('s','r','at1');
    await recoverScheduledRun('s','r','at2');
    expect(send.mock.calls[0][1]).toEqual(send.mock.calls[1][1]);
    expect(send.mock.calls[2][1]).not.toEqual(send.mock.calls[1][1]);
  });
  it('separates runs and refuses to send if durable browser storage fails', async () => {
    send.mockResolvedValue({status:'duplicate'});
    await recoverScheduledRun('s','r1','at1'); await recoverScheduledRun('s','r2','at1');
    expect(send.mock.calls[0][1]).not.toEqual(send.mock.calls[1][1]);
    const fault=vi.spyOn(Storage.prototype,'setItem').mockImplementation(() => { throw new Error('storage'); });
    try { await expect(recoverScheduledRun('s','r3','at1')).rejects.toThrow(); expect(send).toHaveBeenCalledTimes(2); }
    finally { fault.mockRestore(); }
  });
});
