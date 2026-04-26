import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),
    cesium(),
    // Make the WS-203/WS-204 hand-authored CZML demos available under
    // /czml/* in dev and dist. They live at the repo-root czml/demos/ so
    // multiple consumers (renderer, smoke harnesses) can share them.
    viteStaticCopy({
      targets: [
        { src: "../../czml/demos/*.czml", dest: "czml" },
      ],
    }),
  ],
  server: {
    port: 5173,
  },
});
