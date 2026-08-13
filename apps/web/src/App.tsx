import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./shell/AppShell";
import { OverviewPage } from "./pages/OverviewPage";
import { BlueprintStubPage } from "./pages/BlueprintStubPage";
import { S2_LIVE_PATHS, S2_LIVE_ROUTES } from "./pages/s2/routes";
import { RestrictedWidget } from "./marking";
import { isNavPage, NAV_ITEMS } from "./nav";

const WorkshopListPage = lazy(() =>
  import("./pages/WorkshopListPage").then((m) => ({ default: m.WorkshopListPage })),
);
const InboxPage = lazy(() =>
  import("./pages/InboxPage").then((m) => ({ default: m.InboxPage })),
);
const PublishPage = lazy(() =>
  import("./pages/PublishPage").then((m) => ({ default: m.PublishPage })),
);
const CanvasPage = lazy(() =>
  import("./pages/CanvasPage").then((m) => ({ default: m.CanvasPage })),
);
const BuddyPage = lazy(() =>
  import("./pages/BuddyPage").then((m) => ({ default: m.BuddyPage })),
);
const OntologyPage = lazy(() =>
  import("./pages/OntologyPage").then((m) => ({ default: m.OntologyPage })),
);
const DraftInboxPage = lazy(() =>
  import("./pages/DraftInboxPage").then((m) => ({ default: m.DraftInboxPage })),
);
const StudioPage = lazy(() =>
  import("./pages/StudioPage").then((m) => ({ default: m.StudioPage })),
);
const DataPage = lazy(() =>
  import("./pages/DataPage").then((m) => ({ default: m.DataPage })),
);
const ApolloPage = lazy(() =>
  import("./pages/ApolloPage").then((m) => ({ default: m.ApolloPage })),
);
const ModelCatalogPage = lazy(() =>
  import("./pages/s2/ModelCatalogPage").then((m) => ({ default: m.ModelCatalogPage })),
);
const CapacityPage = lazy(() =>
  import("./pages/s2/CapacityPage").then((m) => ({ default: m.CapacityPage })),
);
const AipAssistPage = lazy(() =>
  import("./pages/s2/AipAssistPage").then((m) => ({ default: m.AipAssistPage })),
);
const AipAnalystPage = lazy(() =>
  import("./pages/s2/AipAnalystPage").then((m) => ({ default: m.AipAnalystPage })),
);
const DocumentIntelligencePage = lazy(() =>
  import("./pages/s2/DocumentIntelligencePage").then((m) => ({ default: m.DocumentIntelligencePage })),
);
const WorkspaceMembersPage = lazy(() =>
  import("./pages/WorkspaceMembersPage").then((m) => ({ default: m.WorkspaceMembersPage })),
);
const MyProfilePage = lazy(() =>
  import("./pages/MyProfilePage").then((m) => ({ default: m.MyProfilePage })),
);
const OrgMembershipPage = lazy(() =>
  import("./pages/OrgMembershipPage").then((m) => ({ default: m.OrgMembershipPage })),
);
const InviteAcceptPage = lazy(() =>
  import("./pages/InviteAcceptPage").then((m) => ({ default: m.InviteAcceptPage })),
);
const LocalPlatformPage = lazy(() =>
  import("./pages/LocalPlatformPage").then((m) => ({ default: m.LocalPlatformPage })),
);
const OpsStartGuidePage = lazy(() =>
  import("./pages/OpsStartGuidePage").then((m) => ({ default: m.OpsStartGuidePage })),
);
const SaasProvisioningPage = lazy(() =>
  import("./pages/SaasProvisioningPage").then((m) => ({ default: m.SaasProvisioningPage })),
);

function stub(title: string, id: string, html: string) {
  return <BlueprintStubPage title={title} blueprintId={id} htmlFile={html} />;
}

function PageFallback() {
  return (
    <div className="content-inner" style={{ padding: "40px 20px", textAlign: "center" }}>
      <p className="muted" style={{ fontSize: 13 }}>
        加载中…
      </p>
    </div>
  );
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
          <Route
            index
            element={
              <Suspense fallback={<PageFallback />}>
                <OverviewPage />
              </Suspense>
            }
          />
          <Route
            path="workspace/members"
            element={
              <Suspense fallback={<PageFallback />}>
                <WorkspaceMembersPage />
              </Suspense>
            }
          />
          <Route
            path="settings/profile"
            element={
              <Suspense fallback={<PageFallback />}>
                <MyProfilePage />
              </Suspense>
            }
          />
          <Route
            path="org/membership"
            element={
              <Suspense fallback={<PageFallback />}>
                <OrgMembershipPage />
              </Suspense>
            }
          />
          <Route
            path="org/invite/:token"
            element={
              <Suspense fallback={<PageFallback />}>
                <InviteAcceptPage />
              </Suspense>
            }
          />
          <Route
            path="settings/local-platform"
            element={
              <Suspense fallback={<PageFallback />}>
                <LocalPlatformPage />
              </Suspense>
            }
          />
          <Route
            path="settings/ops-start-guide"
            element={
              <Suspense fallback={<PageFallback />}>
                <OpsStartGuidePage />
              </Suspense>
            }
          />
          <Route
            path="workshop"
            element={
              <Suspense fallback={<PageFallback />}>
                <WorkshopListPage />
              </Suspense>
            }
          />
          <Route
            path="workshop/inbox"
            element={
              <Suspense fallback={<PageFallback />}>
                <InboxPage />
              </Suspense>
            }
          />
          <Route
            path="workshop/canvas"
            element={
              <Suspense fallback={<PageFallback />}>
                <CanvasPage />
              </Suspense>
            }
          />
          <Route
            path="workshop/publish"
            element={
              <Suspense fallback={<PageFallback />}>
                <PublishPage />
              </Suspense>
            }
          />
          <Route
            path="workshop/buddy"
            element={
              <Suspense fallback={<PageFallback />}>
                <RestrictedWidget
                  requiredMarkings={["public"]}
                  userMarkings={["public", "restricted"]}
                >
                  <BuddyPage />
                </RestrictedWidget>
              </Suspense>
            }
          />
          <Route
            path="aip/drafts"
            element={
              <Suspense fallback={<PageFallback />}>
                <DraftInboxPage />
              </Suspense>
            }
          />
          <Route
            path="aip/studio"
            element={
              <Suspense fallback={<PageFallback />}>
                <StudioPage />
              </Suspense>
            }
          />
          <Route
            path="aip/assist"
            element={
              <Suspense fallback={<PageFallback />}>
                <AipAssistPage />
              </Suspense>
            }
          />
          <Route
            path="aip/analyst"
            element={
              <Suspense fallback={<PageFallback />}>
                <AipAnalystPage />
              </Suspense>
            }
          />
          <Route
            path="aip/model-catalog"
            element={
              <Suspense fallback={<PageFallback />}>
                <ModelCatalogPage />
              </Suspense>
            }
          />
          <Route
            path="aip/capacity"
            element={
              <Suspense fallback={<PageFallback />}>
                <CapacityPage />
              </Suspense>
            }
          />
          <Route
            path="aip/doc-intelligence"
            element={
              <Suspense fallback={<PageFallback />}>
                <DocumentIntelligencePage />
              </Suspense>
            }
          />
          {/* W4-E1：pipeline-doc-intel 并入文档智能，残留路径重定向 */}
          <Route path="data/pipeline-doc-intel" element={<Navigate to="/aip/doc-intelligence" replace />} />
          <Route path="pipelines/doc-intel" element={<Navigate to="/aip/doc-intelligence" replace />} />
          <Route
            path="ontology"
            element={
              <Suspense fallback={<PageFallback />}>
                <OntologyPage />
              </Suspense>
            }
          />
          <Route
            path="data"
            element={
              <Suspense fallback={<PageFallback />}>
                <DataPage />
              </Suspense>
            }
          />
          <Route
            path="apollo"
            element={
              <Suspense fallback={<PageFallback />}>
                <ApolloPage />
              </Suspense>
            }
          />
          <Route
            path="apollo/provisioning"
            element={
              <Suspense fallback={<PageFallback />}>
                <SaasProvisioningPage />
              </Suspense>
            }
          />
          {S2_LIVE_ROUTES.map(({ path, Component }) => (
            <Route
              key={path}
              path={path}
              element={
                <Suspense fallback={<PageFallback />}>
                  <Component />
                </Suspense>
              }
            />
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
