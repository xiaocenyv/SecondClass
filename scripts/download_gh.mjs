// 构建辅助：下载 gh CLI 便携版（Windows amd64）到 tools/gh/
import { createWriteStream, mkdirSync, existsSync } from "fs";
import { pipeline } from "stream/promises";
import { execFileSync } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const TOOLSDIR = path.join(ROOT, "tools");
const GHDIR = path.join(TOOLSDIR, "gh");
const ZIP = path.join(TOOLSDIR, "gh.zip");
mkdirSync(TOOLSDIR, { recursive: true });

// 1) 取最新版本号（跟随 /releases/latest 重定向）
const r = await fetch("https://github.com/cli/cli/releases/latest", { redirect: "manual", timeout: 15000 });
const loc = r.headers.get("location") || "";
const m = loc.match(/tag\/(v[\d.]+)$/);
if (!m) { console.error("无法解析 gh 最新版本:", loc); process.exit(1); }
const ver = m[1].replace(/^v/, "");
const url = `https://github.com/cli/cli/releases/download/v${ver}/gh_${ver}_windows_amd64.zip`;
console.log("下载:", url);

// 2) 下载 zip
const resp = await fetch(url, { timeout: 120000 });
if (!resp.ok) { console.error("下载失败 HTTP", resp.status); process.exit(1); }
await pipeline(resp.body, createWriteStream(ZIP));
console.log("zip 保存:", ZIP);

// 3) 解压到 tools/gh/
mkdirSync(GHDIR, { recursive: true });
const pwsh = `Expand-Archive -Force -Path '${ZIP}' -DestinationPath '${GHDIR}'`;
execFileSync("pwsh", ["-NoProfile", "-Command", pwsh]);
const exe = path.join(GHDIR, "bin", "gh.exe");
if (!existsSync(exe)) { console.error("解压后未找到 gh.exe"); process.exit(1); }
console.log("gh.exe ->", exe);
