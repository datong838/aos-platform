import type { IconName } from "../nav";

const PATHS: Record<IconName, string> = {
  home: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1h-5v-6H9v6H4a1 1 0 01-1-1V9.5z"/>',
  plug: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 22v-5M9 7V2M15 7V2M7 13h10a2 2 0 002-2V7a5 5 0 00-10 0v4a2 2 0 002 2z"/>',
  server:
    '<rect x="3" y="4" width="18" height="6" rx="1"/><rect x="3" y="14" width="18" height="6" rx="1"/><circle cx="7" cy="7" r="1" fill="currentColor" stroke="none"/><circle cx="7" cy="17" r="1" fill="currentColor" stroke="none"/>',
  workflow:
    '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path stroke-linecap="round" d="M8 6h8M7 7.5L10 16M17 7.5L14 16"/>',
  layers:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>',
  table:
    '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 10h18M9 10v9M15 10v9"/>',
  git: '<circle cx="6" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="12" r="2"/><path stroke-linecap="round" d="M6 8v8M8 6h5a3 3 0 013 3v0a3 3 0 01-3 3H8"/>',
  spark:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3z"/>',
  heart:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.5l7.5 7 7.5-7a4.5 4.5 0 10-6.4-6.4L12 7.6l-.6-.5A4.5 4.5 0 004.5 12.5z"/>',
  film: '<rect x="3" y="5" width="18" height="14" rx="1"/><path stroke-linecap="round" d="M7 5v14M17 5v14M3 10h4M17 10h4M3 14h4M17 14h4"/>',
  ontology:
    '<circle cx="12" cy="12" r="3"/><path stroke-linecap="round" d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  funnel:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M4 4h16l-5 7v5l-6 4v-9L4 4z"/>',
  wiki: '<path stroke-linecap="round" d="M4 5h16v14H4zM8 9h8M8 13h5"/>',
  stairs:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M4 20h4v-4h4v-4h4V8h4"/>',
  wrench:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>',
  apps: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  inbox:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M4 13h4l2 3h4l2-3h4v6H4v-6zM4 13l2-8h12l2 8"/>',
  graph:
    '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><path stroke-linecap="round" d="M8 12h6M15 7.5l-5 3M15 16.5l-5-3"/>',
  chat: '<path stroke-linecap="round" stroke-linejoin="round" d="M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z"/>',
  bell: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5M10 20a2 2 0 002-2h-2a2 2 0 002 2z"/>',
  chevron:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>',
  check:
    '<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path stroke-linecap="round" d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path stroke-linecap="round" stroke-linejoin="round" d="M21 14.5A8.5 8.5 0 1111.5 3 7 7 0 0021 14.5z"/>',
  monitor:
    '<rect x="3" y="4" width="18" height="12" rx="1"/><path stroke-linecap="round" d="M8 20h8M12 16v4"/>',
  search:
    '<circle cx="11" cy="11" r="7"/><path stroke-linecap="round" d="M20 20l-3-3"/>',
};

export function NavIcon({
  name,
  className = "nav-icon",
}: {
  name: IconName;
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      aria-hidden="true"
      dangerouslySetInnerHTML={{ __html: PATHS[name] || PATHS.home }}
    />
  );
}
