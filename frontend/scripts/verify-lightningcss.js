#!/usr/bin/env node
/**
 * Verify Lightning CSS native binary exists after npm install
 * Prevents build failures from missing platform-specific dependencies
 */

const fs = require('fs');
const path = require('path');

const platform = process.platform;
const arch = process.arch;

// Map platform/arch to Lightning CSS binary name
const binaryMap = {
  'linux-x64': 'lightningcss.linux-x64-gnu.node',
  'linux-arm64': 'lightningcss.linux-arm64-gnu.node',
  'darwin-x64': 'lightningcss.darwin-x64.node',
  'darwin-arm64': 'lightningcss.darwin-arm64.node',
  'win32-x64': 'lightningcss.win32-x64-msvc.node',
};

const key = `${platform}-${arch}`;
const expectedBinary = binaryMap[key];

if (!expectedBinary) {
  console.warn(`Warning: Unknown platform: ${platform}-${arch}`);
  process.exit(0); // Don't fail build
}

// Check if binary exists
const nodeDir = path.join(
  __dirname,
  '..',
  'node_modules',
  'lightningcss',
  'node'
);

const lightningcssPath = path.join(nodeDir, expectedBinary);

console.log(`\n=== Lightning CSS Binary Check ===`);
console.log(`Platform: ${platform}-${arch}`);
console.log(`Expected: ${expectedBinary}`);
console.log(`Path: ${lightningcssPath}`);

if (fs.existsSync(lightningcssPath)) {
  console.log(`Status: Binary found and ready\n`);
  process.exit(0);
} else {
  console.error(`Status: Binary MISSING\n`);

  // Show what files DO exist
  if (fs.existsSync(nodeDir)) {
    const files = fs.readdirSync(nodeDir);
    console.error(`Files in lightningcss/node/:`);
    if (files.length === 0) {
      console.error(`  (directory is empty)`);
    } else {
      files.forEach(f => console.error(`  - ${f}`));
    }
  } else {
    console.error(`Directory doesn't exist: ${nodeDir}`);
  }

  console.error(`\nTroubleshooting:`);
  console.error(`1. Ensure lightningcss-cli is in devDependencies`);
  console.error(`2. Delete package-lock.json and node_modules`);
  console.error(`3. Run: npm install`);
  console.error(`4. Verify Vercel installCommand includes --include=optional`);
  console.error(`5. Check that .npmrc does not have invalid 'optional=true' config\n`);

  // Don't fail build - let Next.js show the error
  process.exit(0);
}
