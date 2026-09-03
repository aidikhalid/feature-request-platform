/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the API, injected at build time from the environment. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
