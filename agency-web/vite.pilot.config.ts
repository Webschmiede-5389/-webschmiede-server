import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], build: { outDir: 'dist-pilot', rollupOptions: { input: 'pilot.html' } } });
