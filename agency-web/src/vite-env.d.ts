/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PUBLIC_SITE_URL: string;
  readonly VITE_N8N_SUPPORT_WEBHOOK_URL: string;
  readonly VITE_N8N_CONTRACT_WEBHOOK_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
