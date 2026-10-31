import test from 'node:test';
import assert from 'node:assert/strict';
import os from 'node:os';
import path from 'node:path';
import fs from 'node:fs/promises';
import {pathsFor,safeProfileName,validPort,optionalLaunchArgs,clearStoppedProfileLock} from './background_chrome.mjs';

test('profile names are bounded',()=>{
  assert.equal(safeProfileName('taobao-brand'),'taobao-brand');
  assert.throws(()=>safeProfileName('../Default'),/invalid-profile-name/);
});

test('daily Chrome profile is rejected',()=>{
  assert.throws(()=>pathsFor({profile:'default','profile-root':path.join(os.homedir(),'Library/Application Support/Google/Chrome')}),/daily-chrome-profile-forbidden/);
});

test('ports are bounded',()=>{
  assert.equal(validPort('9230'),9230);assert.throws(()=>validPort('80'),/invalid-port/);
});

test('session preservation flags are explicit and isolated',()=>{
  assert.deepEqual(optionalLaunchArgs({}),[]);
  assert.deepEqual(optionalLaunchArgs({'disable-background-mode':true}),['--disable-background-mode']);
  assert.deepEqual(optionalLaunchArgs({'restore-last-session':true}),['--restore-last-session']);
});

async function lockFixture(target='test-host-4242',asSymlink=true){
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'background-lock-test-'));
  const p={name:'taobao-agent-service',profile:path.join(root,'taobao-agent-service'),meta:path.join(root,'meta')};
  await fs.mkdir(p.profile);
  const lock=path.join(p.profile,'SingletonLock');
  if(asSymlink)await fs.symlink(target,lock);else await fs.writeFile(lock,'fixture');
  const state={status:'stopped',mode:'headless',profile:p.name,profilePath:p.profile,pid:4242,port:19231};
  return {root,p,state,lock,cleanup:()=>fs.rm(root,{recursive:true,force:true})};
}
const safeLockObservers={host:'test-host',isAlive:async()=>false,profileProcess:async()=>false,portFree:async()=>true};

test('clears only an exact stale lock from this skill stopped instance',async()=>{
  const f=await lockFixture('test-host-4242');
  try{
    assert.equal(await clearStoppedProfileLock(f.p,f.state,safeLockObservers),true);
    await assert.rejects(fs.lstat(f.lock),{code:'ENOENT'});
  }finally{await f.cleanup();}
});

test('clears an exact stopped visible-login lock only for a free target port',async()=>{
  const f=await lockFixture('test-host-4242');
  const visible={...f.state,mode:'visible',port:null};
  try{
    await assert.rejects(clearStoppedProfileLock(f.p,visible,safeLockObservers),/profile-lock-present/);
    assert.equal(await clearStoppedProfileLock(f.p,visible,{...safeLockObservers,nextPort:9230}),true);
    await assert.rejects(fs.lstat(f.lock),{code:'ENOENT'});
  }finally{await f.cleanup();}
  const occupied=await lockFixture('test-host-4242');
  try{
    await assert.rejects(clearStoppedProfileLock(occupied.p,{...visible,profilePath:occupied.p.profile},{...safeLockObservers,nextPort:9230,portFree:async()=>false}),/profile-lock-present/);
    assert.equal(await fs.readlink(occupied.lock),'test-host-4242');
  }finally{await occupied.cleanup();}
});

test('does not clear a lock owned by another host or pid',async()=>{
  for(const target of ['other-host-4242','test-host-9999']){
    const f=await lockFixture(target);
    try{
      await assert.rejects(clearStoppedProfileLock(f.p,f.state,safeLockObservers),/profile-lock-present/);
      assert.equal((await fs.readlink(f.lock)),target);
    }finally{await f.cleanup();}
  }
});

test('does not clear while the recorded process, another profile process, or CDP listener remains',async()=>{
  const cases=[{isAlive:async()=>true},{profileProcess:async()=>true},{portFree:async()=>false}];
  for(const override of cases){
    const f=await lockFixture();
    try{
      await assert.rejects(clearStoppedProfileLock(f.p,f.state,{...safeLockObservers,...override}),/profile-lock-present/);
      assert.equal((await fs.readlink(f.lock)),'test-host-4242');
    }finally{await f.cleanup();}
  }
});

test('does not clear without stopped-state binding or from a non-symlink lock',async()=>{
  const f=await lockFixture();
  try{
    await assert.rejects(clearStoppedProfileLock(f.p,{...f.state,status:'running'},safeLockObservers),/profile-lock-present/);
    assert.equal((await fs.readlink(f.lock)),'test-host-4242');
  }finally{await f.cleanup();}
  const regular=await lockFixture('',false);
  try{
    await assert.rejects(clearStoppedProfileLock(regular.p,regular.state,safeLockObservers),/profile-lock-present/);
    assert.equal(await fs.readFile(regular.lock,'utf8'),'fixture');
  }finally{await regular.cleanup();}
});

test('an absent profile lock is a no-op',async()=>{
  const f=await lockFixture();
  try{
    await fs.unlink(f.lock);
    assert.equal(await clearStoppedProfileLock(f.p,f.state,safeLockObservers),false);
  }finally{await f.cleanup();}
});
