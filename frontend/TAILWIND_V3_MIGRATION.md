# Tailwind CSS v4 to v3 Migration

**Date:** 2025-01-11
**Reason:** v4 native binaries fail to install on Vercel
**Status:** Complete

## Problem

Tailwind CSS v4 (beta) uses native Rust binaries:
- `@tailwindcss/oxide` - Core Tailwind engine
- `lightningcss` - CSS processing

These binaries failed to install on Vercel:
- npm ci with --include=optional flag ineffective
- Only JavaScript files present, no .node native modules
- Build failed: "Cannot find module '../lightningcss.linux-x64-gnu.node'"

## Solution

Downgraded to Tailwind CSS v3.4.17 (stable, pure JavaScript).

## Changes Made

### 1. Dependencies Updated

**Removed:**
- `@tailwindcss/postcss@4.1.14` (from dependencies)
- `tailwindcss@4.1.14` (from dependencies)
- `lightningcss-cli@1.30.1` (from devDependencies)

**Added:**
- `tailwindcss@3.4.17` (to devDependencies)
- `postcss@8.4.49` (to devDependencies)
- `autoprefixer@10.4.20` (to devDependencies)

### 2. Configuration Files

**postcss.config.mjs:**
- Changed from `@tailwindcss/postcss` plugin to standard `tailwindcss` + `autoprefixer`

**tailwind.config.ts:**
- Already present with Tailwind v3 configuration
- Defined content paths for class scanning
- Extended theme with custom colors using CSS variables
- Configured dark mode with class strategy

**app/globals.css:**
- Changed `@import "tailwindcss"` to `@tailwind base/components/utilities`
- Removed `@theme` block (v4-specific, not supported in v3)
- Kept `@layer base` with CSS variables (compatible with v3)

**vercel.json:**
- Removed custom `installCommand` with --include=optional
- Removed `outputDirectory` specification
- Reverted to default npm ci behavior

### 3. Scripts Removed

- Deleted `scripts/verify-lightningcss.js` (no longer needed)
- Removed postinstall script from package.json
- Cleaned up prebuild script (removed lightningcss check)

## Verification

After migration:
- No native binary dependencies
- Pure JavaScript PostCSS processing
- All Tailwind utility classes work identically
- CSS variables preserved
- Dark mode functionality maintained

## Benefits

- Works on all platforms (no binary compilation)
- Faster npm install (no platform-specific packages)
- Production-stable release
- No optional dependency issues
- Simpler build process

## Compatibility

All existing Tailwind utility classes continue to work. The migration is backwards-compatible for:
- Utility classes (bg-*, text-*, flex, grid, etc.)
- Dark mode classes
- Custom CSS variables
- @layer base styles
- Arbitrary values (e.g., w-[32px])

## Future Considerations

When Tailwind v4 reaches stable release and Vercel properly supports native binaries, consider upgrading. Monitor:
- Tailwind v4 stable release announcement
- Vercel binary dependency support improvements
- npm ci optional dependency handling fixes

---

**Migration completed successfully. Build now uses Tailwind v3 with zero native dependencies.**
