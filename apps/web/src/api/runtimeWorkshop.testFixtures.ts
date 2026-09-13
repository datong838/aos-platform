export const tenant = { orgId: 'org-org', projectId: 'dev-project' };
export function fixture() {
  const hash = `sha256:${'a'.repeat(64)}`;
  return { schemaVersion: 'aos.runtime-workshop-catalog/v1', tenant, evaluatedAt: '2026-09-13T10:00:00Z', dataCutoff: null, count: 1,
    items: [{ module: { schema: 'aos.workshop-module/v1', moduleId: 'test.analyst', displayName: '经营参谋', menuLabel: '经营参谋', route: '/workshop/analyst', order: 1 },
      moduleRef: { publisher: 'test', bundleId: 'solution.test', version: '1.0.0', bundleContentHash: hash, moduleArtifactRef: 'bundle://test/content/workshops/test.analyst.json', moduleArtifactHash: hash },
      installationId: '11111111-1111-4111-8111-111111111111', generation: '22222222-2222-4222-8222-222222222222',
      installationRevision: 5, executionEpoch: 3, bindingRevision: 4, resourceOnly: true,
      ui: { title: '经营参谋', signedResourceUrl: `https://ui.example.test/index.html?contentHash=${hash}`, resourceHash: hash, initialRoute: '/workshop/analyst', routeClaims: ['/workshop/analyst'], readOperationClaims: [], commandOperationClaims: [] } }] };
}

