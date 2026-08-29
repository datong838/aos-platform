export type AipFeatureActivationStatus = "active" | "superseded" | "revoked";

export type AipFeatureActivationProjection = {
  featureId: string;
  revision: number;
  contentHash: string;
  status: AipFeatureActivationStatus;
  activatedAt: string;
  expiresAt: string | null;
};

export type AipFeatureActivationList = {
  schemaVersion: "aos.ecommerce-workshop.feature-activation-list/v1";
  tenant: { orgId: string; projectId: string };
  evaluatedAt: string;
  items: AipFeatureActivationProjection[];
};

export type AipFeatureActivationCommandReceipt = {
  schemaVersion: "aos.ecommerce-workshop.feature-activation-command-receipt/v1";
  receiptId: string;
  featureId: string;
  operation: "activate" | "revoke";
  revision: number;
  status: "active" | "revoked";
  contentHash: string;
  createdAt: string;
};

export type AipFeatureActivationCommandResponse = {
  tenant: { orgId: string; projectId: string };
  receipt: AipFeatureActivationCommandReceipt;
  replayed: boolean;
};
