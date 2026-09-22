# DJ direct successor verification（2026-09-22）

## Outcome

`DJ_DIRECT_SUCCESSOR_ACTIVATED`

## Exact authority

| Field | Value |
|---|---|
| predecessor detach | `6ac1c229-2368-4201-a208-4aa96a846e06` / `sha256:e31dc9ae7b95b12cbbc5ad6294030598d8459cc55835c13652928d85c2e3511d` |
| predecessor disable | `b46ecb89-ce38-409b-8153-b502e7739f2b` |
| legacy routes | 308 / group 335 |
| DJ installation | `aca93a08-341f-4bd6-9e94-ed7fde3aed66` |
| DJ generation | `6ce73106-f945-4d34-a818-552303fec308` |
| lock | `sha256:1010c16bb85c06d0dd36e9d33d7de2922b1ab0413e155b4feadf18744c356f89` |
| config | `00eb75bf-6e26-4a02-90dd-e7852cd473ed` / `sha256:4dcc93851a428721d3a0661389aa72b13253037e842f29ac1e9e1e8411ab4d68` |
| prepare op | `dfef9147-6c08-4a7a-b128-6100838048f1` |
| cutover op | `af5b251d-5a47-46c2-a651-866fe0c05018` |
| active routes | 309 / group 336 |
| Host | PID 94313 unique；18181=0 |
| definition | 247 disabled |
| health | baseline 4 → renewals 16（+12）`DJ_HEALTH_OBSERVATION_GREEN` |

## Tests

`pytest … -k 'test_dj_'` → 3 passed。

## Browser

N/A。

## Next wave

DJ saved-snapshot recovery（1/6）。
