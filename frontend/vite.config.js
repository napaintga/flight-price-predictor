import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig(function (_a) {
    var mode = _a.mode;
    var env = loadEnv(mode, process.cwd(), "");
    var apiBaseUrl = env.VITE_API_BASE_URL || "http://localhost:5000";
    return {
        plugins: [react()],
        server: {
            port: 3000,
            proxy: {
                "/api": {
                    target: apiBaseUrl,
                    changeOrigin: true,
                    secure: false
                }
            }
        },
        build: {
            chunkSizeWarningLimit: 800,
            rollupOptions: {
                output: {
                    manualChunks: function (id) {
                        if (!id.includes("node_modules"))
                            return;
                        if (id.includes("react-router-dom"))
                            return "router";
                        if (id.includes("recharts"))
                            return "charts";
                        if (id.includes("react"))
                            return "react";
                        return "vendor";
                    }
                }
            }
        }
    };
});
