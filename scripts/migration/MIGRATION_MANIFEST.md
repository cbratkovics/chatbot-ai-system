# Repository Reorganization Migration Manifest

## Migration Date
2025-10-10

## Migration Type
Gradual Migration (Option 1) - Backwards Compatible

This migration follows a gradual approach where files are copied to new locations while originals are preserved. This allows for thorough testing before removal of old files.

## Files Moved

### Docker Files
```
Dockerfile                    -> docker/dockerfiles/Dockerfile
Dockerfile.production        -> docker/dockerfiles/Dockerfile.production
Dockerfile.test             -> docker/dockerfiles/Dockerfile.test
.dockerignore               -> docker/ignore/.dockerignore
.dockerignore.test          -> docker/ignore/.dockerignore.test
```

### Docker Compose Files
```
docker-compose.yml          -> docker/compose/docker-compose.yml
docker-compose.prod.yml     -> docker/compose/docker-compose.prod.yml
```

### Scripts - Deployment
```
scripts/setup.sh            -> scripts/deployment/setup.sh
```

### Scripts - Validation
```
scripts/production_checklist.sh      -> scripts/validation/production_checklist.sh
scripts/validate_project.sh          -> scripts/validation/validate_project.sh
scripts/verify_setup.sh              -> scripts/validation/verify_setup.sh
scripts/ci/verify_workflow.sh        -> scripts/validation/verify_workflow.sh
scripts/ci/verify_setup.sh           -> scripts/validation/verify_ci_setup.sh
```

### Scripts - Utilities
```
scripts/ci/fix_structure.sh  -> scripts/utils/fix_structure.sh
```

### Documentation
```
docs/guides/BRANCH_COMPARISON.md  -> docs/deployment/BRANCH_COMPARISON.md
```

## Files NOT Moved (Intentionally Left in Place)

### Root Directory (Backwards Compatibility)
```
Dockerfile                   - Kept for existing build processes
Dockerfile.production       - Kept for production builds
Dockerfile.test            - Kept for test builds
.dockerignore              - Kept for Docker builds
.dockerignore.test         - Kept for test builds
docker-compose.yml         - Kept for docker-compose commands
docker-compose.prod.yml    - Kept for production deployments
```

### Scripts Directory
```
scripts/init-db.sql        - Referenced by docker-compose volumes
scripts/backup/            - Referenced by docker-compose volumes
scripts/ci/                - Kept for CI-specific workflows
```

## New Directory Structure Created

```
scripts/
  docker/               (empty - reserved for future Docker utility scripts)
  deployment/           setup.sh
  validation/           production_checklist.sh, validate_project.sh, verify_setup.sh,
                       verify_workflow.sh, verify_ci_setup.sh
  utils/               fix_structure.sh (+ existing manage.py, switch_version.sh)
  migration/           MIGRATION_MANIFEST.md, validate_reorganization.sh, rollback.sh

docker/
  dockerfiles/         Dockerfile, Dockerfile.production, Dockerfile.test
  compose/            docker-compose.yml, docker-compose.prod.yml
  ignore/             .dockerignore, .dockerignore.test

docs/
  deployment/         BRANCH_COMPARISON.md
  development/        (empty - reserved for dev docs)
  architecture/       (existing architecture docs)
  security/           (existing security docs)
  performance/        (existing performance docs)
```

## Files Updated

### Configuration Files
- **Makefile**: No updates required (no references to moved files)
- **.github/workflows/ci.yml**: No updates required (no references to moved files)
- **docker-compose.yml**: No updates required (references non-moved files)
- **docker-compose.prod.yml**: No updates required (references non-moved files)

### Scripts Updated
No scripts required updates as there were no cross-references to moved files detected.

### README.md
No updates required (no references to moved files found)

## Backup Files Created

The following backup files were created before any modifications:
```
Makefile.backup
.github/workflows/ci.yml.backup
docker-compose.yml.backup
docker-compose.prod.yml.backup
README.md.backup
```

## Validation Status

- [x] Directory structure created
- [x] Files copied to new locations
- [x] References analyzed in Makefile (none found)
- [x] References analyzed in GitHub workflows (none found)
- [x] References analyzed in docker-compose (only non-moved files referenced)
- [x] References analyzed in scripts (no cross-references found)
- [x] References analyzed in README (none found)
- [x] Configuration files backed up
- [ ] Validation script created and passed
- [ ] CI/CD pipeline tested
- [ ] Manual testing performed

## Testing Checklist

Before removing original files, verify:

1. **Build Tests**
   - [ ] `make lint` passes
   - [ ] `make test` passes
   - [ ] `make build` passes
   - [ ] `docker build -f docker/dockerfiles/Dockerfile .` succeeds
   - [ ] `docker build -f docker/dockerfiles/Dockerfile.production .` succeeds

2. **Docker Compose Tests**
   - [ ] `docker-compose -f docker/compose/docker-compose.yml config` validates
   - [ ] `docker-compose -f docker/compose/docker-compose.prod.yml config` validates
   - [ ] Services can start using new compose files

3. **Script Execution Tests**
   - [ ] `bash scripts/deployment/setup.sh --help` works
   - [ ] `bash scripts/validation/validate_project.sh` executes
   - [ ] `bash scripts/validation/production_checklist.sh` executes
   - [ ] `bash scripts/validation/verify_setup.sh` executes
   - [ ] `bash scripts/validation/verify_workflow.sh` executes
   - [ ] `bash scripts/utils/fix_structure.sh` executes

4. **CI/CD Pipeline Tests**
   - [ ] GitHub Actions workflow completes successfully
   - [ ] All jobs pass (lint, test, build, docker)

## Known Issues and Warnings

1. **Backwards Compatibility**: Original files remain in place. Any new references should use the new paths.

2. **CI Scripts Directory**: The scripts/ci/ directory still exists with its original files. Consider whether these should be migrated or kept separate.

3. **Docker Context**: All Docker builds still use root context (.) which means Dockerfiles must access files from the root perspective.

4. **Future Work**: Once all systems are verified to work with new structure, the original files in root can be removed and symbolic links can be created if needed.

## Rollback Procedure

If issues arise during testing:

1. **Immediate Rollback**: Original files are still in place, so simply stop using the new locations

2. **Restore Configuration Files** (if modified):
   ```bash
   cp Makefile.backup Makefile
   cp .github/workflows/ci.yml.backup .github/workflows/ci.yml
   cp docker-compose.yml.backup docker-compose.yml
   cp docker-compose.prod.yml.backup docker-compose.prod.yml
   cp README.md.backup README.md
   ```

3. **Remove New Structure**:
   ```bash
   bash scripts/migration/rollback.sh
   ```

4. **Verify System State**: Run existing tests to confirm rollback success

## Next Steps

1. Run comprehensive validation script
2. Test all build processes
3. Test all deployment processes
4. Monitor CI/CD pipeline for any issues
5. After 1-2 weeks of successful operation, create cleanup plan to remove original files
6. Update all documentation to reference new paths
7. Add symbolic links if needed for backwards compatibility

## Migration Success Criteria

The migration is considered successful when:
- [x] All new directories created
- [x] All files copied to new locations
- [x] All configuration files analyzed and backed up
- [ ] Validation script passes all checks
- [ ] Make targets execute without errors
- [ ] Docker builds execute without errors
- [ ] Scripts execute from new locations without errors
- [ ] No broken references found
- [ ] CI/CD pipeline passes
- [ ] Manual testing confirms functionality

## Contact and Support

For issues or questions about this migration:
- Review this manifest
- Check rollback procedures
- Consult backup files
- Review git history for changes

## Version History

- **2025-10-10**: Initial migration completed
  - Created directory structure
  - Copied all files to new locations
  - Created migration manifest
  - Created validation and rollback scripts
