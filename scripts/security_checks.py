#!/usr/bin/env python3
"""
Enterprise Security Validation Scripts
Comprehensive security checks for CI/CD pipeline
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SecurityFinding:
    """Security finding data structure"""
    severity: str
    category: str
    title: str
    description: str
    file_path: str
    line_number: int | None = None
    cve_id: str | None = None
    recommendation: str | None = None

@dataclass
class SecurityReport:
    """Security report summary"""
    total_findings: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    findings: list[SecurityFinding]
    compliance_status: dict[str, bool]

class LicenseChecker:
    """License compliance checker"""
    
    APPROVED_LICENSES = {
        'MIT', 'Apache-2.0', 'BSD-3-Clause', 'BSD-2-Clause', 
        'ISC', 'PostgreSQL', 'Python Software Foundation License'
    }
    
    FORBIDDEN_LICENSES = {
        'GPL-3.0', 'GPL-2.0', 'AGPL-3.0', 'LGPL-3.0'
    }
    
    def __init__(self):
        self.violations = []
        
    def check_licenses(self, licenses_file: str) -> list[SecurityFinding]:
        """Check license compliance"""
        findings = []
        
        try:
            with open(licenses_file) as f:
                licenses_data = json.load(f)
                
            for package in licenses_data:
                license_name = package.get('License', 'Unknown')
                package_name = package.get('Name', 'Unknown')
                
                if license_name in self.FORBIDDEN_LICENSES:
                    findings.append(SecurityFinding(
                        severity='HIGH',
                        category='LICENSE_VIOLATION',
                        title=f'Forbidden license: {license_name}',
                        description=f'Package {package_name} uses forbidden license {license_name}',
                        file_path='config/requirements/base.txt',
                        recommendation=f'Replace {package_name} with alternative having approved license'
                    ))
                    
                elif license_name not in self.APPROVED_LICENSES and license_name != 'Unknown':
                    findings.append(SecurityFinding(
                        severity='MEDIUM',
                        category='LICENSE_REVIEW',
                        title=f'Unapproved license: {license_name}',
                        description=f'Package {package_name} uses unapproved license {license_name}',
                        file_path='config/requirements/base.txt',
                        recommendation=f'Review license {license_name} for compliance'
                    ))
                    
        except Exception as e:
            logger.error(f"Error checking licenses: {e}")
            
        return findings

class SecretScanner:
    """Secret detection in code"""
    
    SECRET_PATTERNS = {
        'AWS_ACCESS_KEY': r'AKIA[0-9A-Z]{16}',
        'AWS_SECRET_KEY': r'[0-9a-zA-Z/+]{40}',
        'PRIVATE_KEY': r'-----BEGIN PRIVATE KEY-----',
        'API_KEY': r'api[_-]?key["\']?\s*[:=]\s*["\']?[0-9a-zA-Z]{32,}',
        'PASSWORD': r'password["\']?\s*[:=]\s*["\'][^"\']{8,}["\']',
        'JWT_TOKEN': r'eyJ[0-9a-zA-Z_-]+\.[0-9a-zA-Z_-]+\.[0-9a-zA-Z_-]+',
        'DATABASE_URL': r'(postgresql|mysql|mongodb)://[^:]+:[^@]+@[^/]+/[^?\s]+',
    }
    
    def scan_directory(self, directory: str) -> list[SecurityFinding]:
        """Scan directory for secrets"""
        findings = []
        
        for root, dirs, files in os.walk(directory):
            # Skip hidden directories and common build directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv']]
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.yml', '.yaml', '.json', '.env')):
                    file_path = os.path.join(root, file)
                    findings.extend(self._scan_file(file_path))
                    
        return findings
    
    def _scan_file(self, file_path: str) -> list[SecurityFinding]:
        """Scan individual file for secrets"""
        findings = []
        
        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
                
                for line_num, line in enumerate(lines, 1):
                    for secret_type, pattern in self.SECRET_PATTERNS.items():
                        matches = re.finditer(pattern, line, re.IGNORECASE)
                        for _match in matches:
                            # Skip if it's in a comment or test file
                            if self._is_false_positive(line, file_path):
                                continue
                                
                            findings.append(SecurityFinding(
                                severity='CRITICAL',
                                category='SECRET_EXPOSURE',
                                title=f'Potential {secret_type} found',
                                description=f'Potential secret of type {secret_type} found in {file_path}',
                                file_path=file_path,
                                line_number=line_num,
                                recommendation='Remove hardcoded secret and use environment variables'
                            ))
                            
        except Exception as e:
            logger.error(f"Error scanning file {file_path}: {e}")
            
        return findings
    
    def _is_false_positive(self, line: str, file_path: str) -> bool:
        """Check if finding is likely a false positive"""
        # Skip comments
        if line.strip().startswith('#') or line.strip().startswith('//'):
            return True
            
        # Skip test files with example data
        if 'test' in file_path.lower() or 'example' in line.lower():
            return True
            
        # Skip placeholder values
        if any(placeholder in line.lower() for placeholder in ['example', 'placeholder', 'your_key_here', 'xxx']):
            return True
            
        return False

class VulnerabilityScanner:
    """Vulnerability scanning using multiple tools"""
    
    def scan_dependencies(self) -> list[SecurityFinding]:
        """Scan dependencies for vulnerabilities"""
        findings = []
        
        # Safety check for Python packages
        try:
            result = subprocess.run(['safety', 'check', '--json'], 
                                  capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0 and result.stdout:
                safety_data = json.loads(result.stdout)
                for vuln in safety_data:
                    findings.append(SecurityFinding(
                        severity=self._map_safety_severity(vuln.get('vulnerability_id')),
                        category='DEPENDENCY_VULNERABILITY',
                        title=f"Vulnerable package: {vuln.get('package')}",
                        description=vuln.get('advisory'),
                        file_path='config/requirements/base.txt',
                        cve_id=vuln.get('vulnerability_id'),
                        recommendation=f"Upgrade to version {vuln.get('analyzed_version')}"
                    ))
                    
        except Exception as e:
            logger.error(f"Safety scan failed: {e}")
            
        return findings
    
    def _map_safety_severity(self, vuln_id: str) -> str:
        """Map Safety vulnerability ID to severity"""
        # This is a simplified mapping - in production, you'd use CVE scores
        if not vuln_id:
            return 'MEDIUM'
        
        # High severity patterns
        if any(pattern in vuln_id.lower() for pattern in ['rce', 'sql', 'xss', 'csrf']):
            return 'HIGH'
        
        return 'MEDIUM'

class ComplianceChecker:
    """Compliance validation for various standards"""
    
    def check_gdpr_compliance(self) -> dict[str, bool]:
        """Check GDPR compliance indicators"""
        compliance = {}
        
        # Check for privacy policy
        compliance['privacy_policy_exists'] = os.path.exists('PRIVACY.md') or os.path.exists('docs/privacy.md')
        
        # Check for data handling documentation
        compliance['data_handling_documented'] = self._search_for_patterns([
            'personal data', 'data processing', 'data subject rights'
        ])
        
        # Check for consent mechanisms
        compliance['consent_mechanism'] = self._search_for_patterns([
            'consent', 'opt-in', 'opt-out', 'cookie consent'
        ])
        
        # Check for data retention policies
        compliance['data_retention_policy'] = self._search_for_patterns([
            'data retention', 'delete after', 'retention period'
        ])
        
        return compliance
    
    def check_soc2_compliance(self) -> dict[str, bool]:
        """Check SOC 2 compliance indicators"""
        compliance = {}
        
        # Security controls
        compliance['access_controls'] = self._check_access_controls()
        compliance['encryption_at_rest'] = self._check_encryption_at_rest()
        compliance['encryption_in_transit'] = self._check_encryption_in_transit()
        compliance['audit_logging'] = self._check_audit_logging()
        compliance['incident_response'] = os.path.exists('INCIDENT_RESPONSE.md')
        
        return compliance
    
    def _search_for_patterns(self, patterns: list[str]) -> bool:
        """Search for patterns in codebase"""
        for root, _dirs, files in os.walk('.'):
            for file in files:
                if file.endswith(('.py', '.md', '.rst', '.txt')):
                    try:
                        with open(os.path.join(root, file), errors='ignore') as f:
                            content = f.read().lower()
                            if any(pattern.lower() in content for pattern in patterns):
                                return True
                    except (OSError, UnicodeDecodeError):
                        continue
        return False
    
    def _check_access_controls(self) -> bool:
        """Check for access control implementation"""
        # Look for authentication/authorization code
        return self._search_for_patterns(['@login_required', 'authenticate', 'authorize', 'rbac'])
    
    def _check_encryption_at_rest(self) -> bool:
        """Check for encryption at rest"""
        return self._search_for_patterns(['encrypt', 'AES', 'cipher', 'encryption_key'])
    
    def _check_encryption_in_transit(self) -> bool:
        """Check for encryption in transit"""
        return self._search_for_patterns(['https', 'tls', 'ssl', 'secure_transport'])
    
    def _check_audit_logging(self) -> bool:
        """Check for audit logging"""
        return self._search_for_patterns(['audit_log', 'security_log', 'access_log'])

class SecurityReportGenerator:
    """Generate comprehensive security reports"""
    
    def __init__(self):
        self.license_checker = LicenseChecker()
        self.secret_scanner = SecretScanner()
        self.vuln_scanner = VulnerabilityScanner()
        self.compliance_checker = ComplianceChecker()
    
    def generate_report(self, output_file: str = 'security-report.json') -> SecurityReport:
        """Generate comprehensive security report"""
        logger.info("Starting security assessment...")
        
        all_findings = []
        
        # License compliance check
        if os.path.exists('licenses.json'):
            logger.info("Checking license compliance...")
            all_findings.extend(self.license_checker.check_licenses('licenses.json'))
        
        # Secret scanning
        logger.info("Scanning for secrets...")
        all_findings.extend(self.secret_scanner.scan_directory('.'))
        
        # Vulnerability scanning
        logger.info("Scanning dependencies for vulnerabilities...")
        all_findings.extend(self.vuln_scanner.scan_dependencies())
        
        # Compliance checks
        logger.info("Checking compliance...")
        gdpr_compliance = self.compliance_checker.check_gdpr_compliance()
        soc2_compliance = self.compliance_checker.check_soc2_compliance()
        
        # Generate summary
        severity_counts = {
            'CRITICAL': len([f for f in all_findings if f.severity == 'CRITICAL']),
            'HIGH': len([f for f in all_findings if f.severity == 'HIGH']),
            'MEDIUM': len([f for f in all_findings if f.severity == 'MEDIUM']),
            'LOW': len([f for f in all_findings if f.severity == 'LOW'])
        }
        
        report = SecurityReport(
            total_findings=len(all_findings),
            critical_findings=severity_counts['CRITICAL'],
            high_findings=severity_counts['HIGH'],
            medium_findings=severity_counts['MEDIUM'],
            low_findings=severity_counts['LOW'],
            findings=all_findings,
            compliance_status={
                'gdpr': gdpr_compliance,
                'soc2': soc2_compliance
            }
        )
        
        # Save report
        self._save_report(report, output_file)
        
        # Print summary
        self._print_summary(report)
        
        return report
    
    def _save_report(self, report: SecurityReport, output_file: str):
        """Save report to file"""
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_findings': report.total_findings,
                'critical_findings': report.critical_findings,
                'high_findings': report.high_findings,
                'medium_findings': report.medium_findings,
                'low_findings': report.low_findings
            },
            'findings': [
                {
                    'severity': f.severity,
                    'category': f.category,
                    'title': f.title,
                    'description': f.description,
                    'file_path': f.file_path,
                    'line_number': f.line_number,
                    'cve_id': f.cve_id,
                    'recommendation': f.recommendation
                }
                for f in report.findings
            ],
            'compliance': report.compliance_status
        }
        
        with open(output_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"Security report saved to {output_file}")
    
    def _print_summary(self, report: SecurityReport):
        """Print security report summary"""
        print("\n" + "="*60)
        print("SECURITY ASSESSMENT SUMMARY")
        print("="*60)
        print(f"Total Findings: {report.total_findings}")
        print(f"Critical: {report.critical_findings}")
        print(f"High: {report.high_findings}")
        print(f"Medium: {report.medium_findings}")
        print(f"Low: {report.low_findings}")
        
        print("\nCOMPLIANCE STATUS:")
        print("-" * 20)
        
        for standard, checks in report.compliance_status.items():
            print(f"\n{standard.upper()}:")
            for check, status in checks.items():
                status_symbol = "✅" if status else "❌"
                print(f"  {status_symbol} {check.replace('_', ' ').title()}")
        
        # Exit with error code if critical or high findings
        if report.critical_findings > 0 or report.high_findings > 0:
            print(f"\n❌ Security assessment failed: {report.critical_findings} critical, {report.high_findings} high severity findings")
            sys.exit(1)
        else:
            print("\n✅ Security assessment passed")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Enterprise Security Validation')
    parser.add_argument('--output', '-o', default='security-report.json',
                      help='Output file for security report')
    parser.add_argument('--licenses', help='Path to licenses.json file')
    parser.add_argument('--fail-on-high', action='store_true',
                      help='Fail on high severity findings')
    
    args = parser.parse_args()
    
    generator = SecurityReportGenerator()
    report = generator.generate_report(args.output)
    
    # Exit based on findings severity
    if args.fail_on_high and (report.critical_findings > 0 or report.high_findings > 0):
        sys.exit(1)
    elif report.critical_findings > 0:
        sys.exit(1)
    
    sys.exit(0)

if __name__ == '__main__':
    main()