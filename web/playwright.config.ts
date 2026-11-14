import {defineConfig,devices} from "@playwright/test";
const existingServer = process.env.PLAYWRIGHT_BASE_URL;
export default defineConfig({
 testDir:"./tests",fullyParallel:false,workers:process.env.CI?2:1,timeout:30000,
 use:{baseURL:existingServer || "http://127.0.0.1:3100",trace:"retain-on-failure",...devices["Desktop Chrome"],channel:process.env.CI?undefined:"msedge",launchOptions:{args:["--disable-gpu"]}},
 webServer:existingServer ? undefined : {command:"node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3100",url:"http://127.0.0.1:3100",reuseExistingServer:!process.env.CI,timeout:120000},
});
