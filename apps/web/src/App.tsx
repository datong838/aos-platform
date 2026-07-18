import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./shell/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { WorkshopListPage } from "./pages/WorkshopListPage";
import { InboxPage } from "./pages/InboxPage";
import { PublishPage } from "./pages/PublishPage";
import { CanvasPage } from "./pages/CanvasPage";
import { BuddyPage } from "./pages/BuddyPage";
import { OntologyPage } from "./pages/OntologyPage";
import { DraftInboxPage } from "./pages/DraftInboxPage";
import { LogicPage } from "./pages/LogicPage";
import { StudioPage } from "./pages/StudioPage";
import { DataPage } from "./pages/DataPage";
import { ApolloPage } from "./pages/ApolloPage";
import { CapabilityPage } from "./pages/CapabilityPage";
import { BlueprintStubPage } from "./pages/BlueprintStubPage";
import { S2_LIVE_PATHS, S2_LIVE_ROUTES } from "./pages/s2/routes";
import { RestrictedWidget } from "./marking";
import { isNavPage, NAV_ITEMS } from "./nav";

function stub(title: string, id: string, html: string) {
  return <BlueprintStubPage title={title} blueprintId={id} htmlFile={html} />;
}

/** Remaining s2 paths — honest stubs */
const S2_STUB_ROUTES = NAV_ITEMS.filter(isNavPage).filter(
  (p) => p.status === "s2" && !S2_LIVE_PATHS.has(p.path),
);

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="workshop" element={<WorkshopListPage />} />
          <Route path="workshop/inbox" element={<InboxPage />} />
          <Route path="workshop/canvas" element={<CanvasPage />} />
          <Route path="workshop/publish" element={<PublishPage />} />
          <Route
            path="workshop/buddy"
            element={
              <RestrictedWidget
                requiredMarkings={["public"]}
                userMarkings={["public", "restricted"]}
              >
                <BuddyPage />
              </RestrictedWidget>
            }
          />
          <Route path="aip/drafts" element={<DraftInboxPage />} />
          <Route path="aip/logic" element={<LogicPage />} />
          <Route path="aip/studio" element={<StudioPage />} />
          <Route path="aip/capabilities" element={<CapabilityPage />} />
          <Route path="ontology" element={<OntologyPage />} />
          <Route path="data" element={<DataPage />} />
          <Route path="apollo" element={<ApolloPage />} />
          {S2_LIVE_ROUTES.map(({ path, Component }) => (
            <Route key={path} path={path} element={<Component />} />
          ))}
          {S2_STUB_ROUTES.map((p) => (
            <Route
              key={p.id}
              path={p.path.replace(/^\//, "")}
              element={stub(p.label, p.id, `${p.id}.html`)}
            />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
