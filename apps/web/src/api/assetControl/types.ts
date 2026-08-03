/** JSON values accepted by the canonical API error details payload. */
export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };

export type Sha256 = `sha256:${string}`;
export type IsoDateTime = string;

export type BundleKind =
  | "DomainPack"
  | "SolutionPack"
  | "VerticalPack"
  | "PlatformAdapterPack"
  | "PluginPack";

export interface RequestedBundle {
  publisher: string;
  id: string;
  version: string;
}

export interface CurrentInstallationRef {
  installationId: string;
  revision: number;
  lockHash: Sha256;
  overlayRevision: string;
}

export interface CanonicalCompositionRequest {
  requested: RequestedBundle[];
  platformApiVersion: string;
  platformRelease: string;
  environment: "dev" | "staging" | "prod";
}

export interface CompositionRequest extends CanonicalCompositionRequest {
  registrySnapshotHash?: Sha256 | null;
  currentInstallationRef?: CurrentInstallationRef | null;
}

export interface DependencyConstraint {
  publisher: string;
  id: string;
  version: string;
}

export interface ConflictConstraint {
  publisher: string;
  id: string;
  version: string | null;
}

export interface CapabilitySet {
  provides: string[];
  requires: string[];
}

export interface PermissionSet {
  roles: string[];
  markings: string[];
  dataScopes: string[];
  actionTypes: string[];
}

export interface MigrationDescriptor {
  planRef: string | null;
  downgradePolicy: "retain-canonical";
}

export interface ApiContributionClaim {
  kind: "api";
  method: string;
  path: string;
  operationId: string;
  mode: "exclusive";
}

export interface NavigationContributionClaim {
  kind: "navigation";
  route: string;
  mode: "exclusive" | "shared";
}

export interface UiContributionClaim {
  kind: "ui";
  slot: string;
  id: string;
  mode: "exclusive" | "shared";
}

export type ContributionClaim =
  | ApiContributionClaim
  | NavigationContributionClaim
  | UiContributionClaim;

export interface ResolvedBundle {
  publisher: string;
  id: string;
  version: string;
  kind: BundleKind;
  contentHash: Sha256;
  signatureFingerprint: Sha256;
  releaseEvidenceRevision: Sha256;
  dependencies: DependencyConstraint[];
  optionalDependencies: DependencyConstraint[];
  conflicts: ConflictConstraint[];
  capabilities: CapabilitySet;
  permissions: PermissionSet;
  migration: MigrationDescriptor;
  contributions: ContributionClaim[];
  selectionReason: "requested" | "dependency";
}

export interface ResolvedEdge {
  fromPublisher: string;
  fromId: string;
  fromVersion: string;
  toPublisher: string;
  toId: string;
  toVersion: string;
  constraint: string;
  optional: boolean;
}

export interface CapabilityProvider {
  capability: string;
  publisher: string;
  id: string;
  version: string;
}

export interface PermissionDiff {
  baseline: PermissionSet;
  target: PermissionSet;
  added: PermissionSet;
  removed: PermissionSet;
  unchanged: PermissionSet;
}

export interface MigrationStep {
  publisher: string;
  id: string;
  version: string;
  planRef: string;
  downgradePolicy: "retain-canonical";
}

export interface MigrationChange {
  publisher: string;
  id: string;
  before: MigrationStep;
  after: MigrationStep;
}

export interface MigrationPlanDiff {
  baseline: MigrationStep[];
  target: MigrationStep[];
  added: MigrationStep[];
  removed: MigrationStep[];
  changed: MigrationChange[];
}

export interface ContributionBinding {
  publisher: string;
  id: string;
  version: string;
  claim: ContributionClaim;
}

export interface ContributionDiff {
  baseline: ContributionBinding[];
  target: ContributionBinding[];
  added: ContributionBinding[];
  removed: ContributionBinding[];
  unchanged: ContributionBinding[];
}

export interface CompositionLockPayload {
  lockSchemaVersion: "aos.dev/composition-lock/v1alpha1";
  resolverVersion: "aos-resolver/1.0.0";
  request: CanonicalCompositionRequest;
  registrySnapshotHash: Sha256;
  resolved: ResolvedBundle[];
  edges: ResolvedEdge[];
  capabilityProviders: CapabilityProvider[];
  permissionDiff: PermissionDiff;
  migrationPlan: MigrationPlanDiff;
  contributionDiff: ContributionDiff;
  currentInstallationRef: CurrentInstallationRef | null;
}

export interface StoredCompositionLock {
  compositionId: string;
  revision: number;
  payload: CompositionLockPayload;
  lockHash: Sha256;
  permissionDiffHash: Sha256;
  migrationPlanHash: Sha256;
  contributionDiffHash: Sha256;
  createdAt: IsoDateTime;
}

export type InstallationState =
  | "draft"
  | "submitted"
  | "approved"
  | "rejected"
  | "applied"
  | "active"
  | "rolled_back";

export interface CreateInstallationRequest {
  compositionId: string;
  lockRevision: number;
  overlayRevision: string;
  displayName: string;
}

export type EmptyInstallationActionRequest = Record<string, never>;

export interface ApproveInstallationRequest {
  lockHash: Sha256;
  permissionDiffHash: Sha256;
  migrationPlanHash: Sha256;
  contributionDiffHash: Sha256;
}

export interface RejectInstallationRequest {
  reason: string;
}

export interface RollbackInstallationRequest {
  reason: string;
}

export interface InstallationRevision {
  installationId: string;
  revision: number;
  parentRevision: number | null;
  state: InstallationState;
  compositionId: string;
  lockRevision: number;
  lockHash: Sha256;
  permissionDiffHash: Sha256;
  migrationPlanHash: Sha256;
  contributionDiffHash: Sha256;
  overlayRevision: string;
  requestedBy: string;
  decisionId: string | null;
  createdAt: IsoDateTime;
}

export interface InstallationDecision {
  decisionId: string;
  installationId: string;
  submittedRevision: number;
  decision: "approved" | "rejected";
  actor: string;
  lockHash: Sha256;
  permissionDiffHash: Sha256;
  migrationPlanHash: Sha256;
  contributionDiffHash: Sha256;
  reason: string | null;
  createdAt: IsoDateTime;
}

export interface InstallationEventEvidence {
  type: "dry_apply" | "verification" | "rollback";
  evidenceRef: string;
  evidenceHash: Sha256;
  status: "valid" | "invalid";
  observedAt: IsoDateTime;
}

export interface InstallationEvent {
  sequence: number;
  fromRevision: number | null;
  toRevision: number;
  fromState: InstallationState | null;
  toState: InstallationState;
  actor: string;
  reason: string | null;
  evidence: InstallationEventEvidence | null;
  createdAt: IsoDateTime;
}

export interface InstallationListItem {
  installationId: string;
  displayName: string;
  state: InstallationState;
  currentRevision: number;
  activeRevision: number | null;
  previousActiveRevision: number | null;
  etagVersion: number;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

export interface InstallationRecord extends InstallationListItem {
  current: InstallationRevision;
  decision: InstallationDecision | null;
  events: InstallationEvent[];
}

export type InstallationResponse = InstallationRecord;

export interface InstallationListResponse {
  items: InstallationListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details: { [key: string]: JsonValue } | null;
  traceId: string;
}
