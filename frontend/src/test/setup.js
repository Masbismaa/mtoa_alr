// disiapin sebelum tiap file test Vitest (vite.config.js -> test.setupFiles)
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  document.head.innerHTML = "";
  delete window.AlrStatusBar;
});
