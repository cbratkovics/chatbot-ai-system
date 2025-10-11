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
const lightningcssPath = path.join(
  __dirname,
  '..',
  'node_modules',
  'lightningcss',
  'node',
  expectedBinary
);

if (fs.existsSync(lightningcssPath)) {
  console.log(`Lightning CSS binary found: ${expectedBinary}`);
  process.exit(0);
} else {
  console.error(`Lightning CSS binary MISSING: ${expectedBinary}`);
  console.error(`Expected at: ${lightningcssPath}`);
  console.error('\nTroubleshooting:');
  console.error('1. Delete node_modules and package-lock.json');
  console.error('2. Run: npm install');
  console.error('3. Ensure .npmrc has optional=true');
  console.error('4. Check that Node version matches package.json engines');

  // Don't fail build - let Next.js fail with better error message
  process.exit(0);
}
