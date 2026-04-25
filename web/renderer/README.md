# `@almighty/renderer`

Resium 3D battlespace + EXCON / white-cell / AAR consoles for Almighty.

> **Banner:** every route renders `UNCLASSIFIED — FOR DEMONSTRATION PURPOSES ONLY` at top and bottom. The strip lives in `App.tsx` around `<Outlet/>` so child routes cannot accidentally drop it.

## Stack

- Vite 6 + React 18 + TypeScript
- Resium + Cesium 1.123
- React Router v6
- pnpm

## Develop

```bash
cp .env.example .env
# Add your Cesium ion token to VITE_CESIUM_ION_TOKEN
pnpm install
pnpm dev
```

Open `http://localhost:5173/demo/scenarios/demo` to see the Nashville scene with banners.

## Cesium ion token

The scaffold reads `VITE_CESIUM_ION_TOKEN` from `import.meta.env`. Vite only exposes env vars prefixed with `VITE_` to client code, which is why this var is the `VITE_`-prefixed form of the spec's `CESIUM_ION_TOKEN`.

**Default behavior:** if the token is set, it is assigned to `Ion.defaultAccessToken` on module load. If unset, Cesium falls back to its default unauthenticated assets, which works for the scaffold but will not satisfy the WS-501 smoke test (Nashville terrain + imagery quality).

**Self-hosted-assets fallback (not yet implemented):** for air-gapped or token-free deployments, replace `vite-plugin-cesium` with a manual `vite-plugin-static-copy` step that bundles `node_modules/cesium/Build/Cesium/{Workers,Assets,Widgets,ThirdParty}` into `/cesium/` and set `window.CESIUM_BASE_URL = "/cesium/"` in `main.tsx` before the first Cesium import. Substitute `Cesium.createWorldTerrainAsync` with the offline ellipsoid terrain provider and a tile layer pointing at a self-hosted basemap. This path is documented but not wired — pursue when WS-301 / per-tenant deployment makes ion infeasible.

## Structure

```
src/
  main.tsx            React entry; mounts the router.
  router.tsx          Route table.
  App.tsx             Banner + <Outlet/> shell.
  components/
    Banner.tsx        UNCLASSIFIED strip (top + bottom).
    CesiumScene.tsx   Resium <Viewer/> centered on Nashville.
  layouts/
    Excon.tsx         3-column CSS grid: sidebar | map | actions.
  routes/
    Index.tsx         "/" — placeholder scenario picker.
    ScenarioRoot.tsx  "/:tenantId/scenarios/:scenarioId" — Excon shell with the Cesium map mounted.
```

## Smoke test (WS-501 DoD)

1. `pnpm dev`
2. Visit `http://localhost:5173/demo/scenarios/demo`.
3. Confirm: Nashville terrain visible (camera centered ~36.18°N, 86.78°W at 8 km altitude, looking down). Both banners present, top and bottom, ~10px tall, light-green background, dark text.
