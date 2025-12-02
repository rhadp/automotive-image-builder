# Booting Tests

This test suite validates that the system boots into a healthy and secure state.
It includes checks for kernel logs, systemd status, and SELinux configuration.
All tests run automatically on boot through a **test-runner.service**.

---

## Tests

### 1. dmesg does not contain critical warnings/errors
**Description:**
This test checks that `dmesg` output does not contain any critical warnings or errors after boot.
A clean `dmesg` ensures the kernel and hardware initialized properly without unexpected failures.

---

### 2. systemd is running
**Description:**
This test verifies that `systemd` is running correctly and that no units have failed.
A healthy `systemd` state ensures services and targets required by the system are functioning as expected.

---

### 3. SELinux is enabled on all images
**Description:**
This test checks that SELinux is enabled and running in **enforcing** mode by default.
This ensures that mandatory access control policies are applied for improved system security.

---

### 4. RPM database is initialized properly
**Description:**
This test checks that RPM database is initialized properly and glibc package is installed.

---


## Test Runner

All tests are executed by a wrapper script (`run-all.sh`) that:
1. Runs each individual test in sequence.
2. Captures the results (pass/fail and logs) into a single logfile (`/var/tmp/tests/test-results.txt`).
3. Returns a consolidated summary at the end.

---

## Expected Results
- `dmesg` contains no critical warnings or errors.
- `systemd` reports no failed services.
- SELinux is enabled and enforcing.
- RPM database initialized properly.

If any of these checks fail, the boot process may be considered unhealthy or insecure.
