import { EcommerceWorkshopHost } from "../../../components/workshop";
import { useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useOptionalRuntimeWorkshopCatalog } from '../../../components/extensions/RuntimeWorkshopCatalog';
import { RuntimeWorkshopHost } from '../../../components/extensions/RuntimeWorkshopHost';
import { findInstalledWorkshopRoute, useEcommerceWorkshopCatalog } from '../../../components/workshop/EcommerceWorkshopCatalogContext';

export function EcommerceWorkshopEntryRoute() {
  const runtime = useOptionalRuntimeWorkshopCatalog();
  const legacy = useEcommerceWorkshopCatalog();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const latest = useRef({ runtime, legacy, pathname });
  latest.current = { runtime, legacy, pathname };
  if (runtime === null) return <EcommerceWorkshopHost />;
  const matches = runtime.items.filter(entry => entry.module.route === pathname);
  const legacyMatch = findInstalledWorkshopRoute(legacy.modules, pathname);
  const reload = () => { runtime.reload(); legacy.reload(); };
  if (matches.length > 1 || (matches.length > 0 && legacyMatch)) {
    return <section role="alert">工作台入口声明存在冲突，请核对安装状态。<button onClick={reload}>重新读取目录</button></section>;
  }
  if (matches.length === 1) {
    if (runtime.phase !== 'ready' || !['ready', 'empty'].includes(legacy.phase)) {
      return <section role="status">正在核对工作台入口，暂不加载页面。<button onClick={reload}>重新读取目录</button></section>;
    }
    const entry = matches[0], fingerprint = JSON.stringify(entry);
    return <RuntimeWorkshopHost entry={entry} navigate={navigate} isCurrent={() => {
      const value = latest.current;
      return value.pathname === entry.module.route && value.runtime?.phase === 'ready'
        && ['ready', 'empty'].includes(value.legacy.phase)
        && !findInstalledWorkshopRoute(value.legacy.modules, entry.module.route)
        && value.runtime.items.filter(item => JSON.stringify(item) === fingerprint).length === 1;
    }} />;
  }
  if (!legacyMatch && (runtime.phase === 'loading' || runtime.phase === 'failed')) {
    return <section role="status">{runtime.phase === 'loading' ? '正在读取已安装工作台目录…' : '已安装工作台目录暂不可用。'}
      <button onClick={reload}>重新读取目录</button></section>;
  }
  return <EcommerceWorkshopHost onCatalogReload={reload} />;
}
