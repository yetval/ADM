#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const env = { ...process.env };
env.PYTHONPATH = env.PYTHONPATH ? `${root}${path.delimiter}${env.PYTHONPATH}` : root;

const candidates = process.platform === "win32" ? ["py", "python", "python3"] : ["python3", "python"];
let result = null;

for (const python of candidates) {
  const args = python === "py"
    ? ["-3", "-m", "awsdockermanager.cli", ...process.argv.slice(2)]
    : ["-m", "awsdockermanager.cli", ...process.argv.slice(2)];
  result = spawnSync(python, args, { cwd: process.cwd(), env, stdio: "inherit" });
  if (result.error && result.error.code === "ENOENT") {
    continue;
  }
  if (result.error) {
    console.error(`ADM failed to start: ${result.error.message}`);
    process.exit(1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

console.error("ADM requires Python 3.10+ on PATH. Install python3 and try again.");
process.exit(1);
