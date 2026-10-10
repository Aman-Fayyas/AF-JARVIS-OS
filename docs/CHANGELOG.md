# 0.1.0-alpha source checkpoint

## Boot audit continuation

- Verified original ZIP/source identity; retained existing architecture.
- Fixed session failure propagation, login-hook idempotence, user/PAM/X11/process dependencies and graphical target.
- Corrected generation cleanup, reload rollback, provider validation, privacy races, Unicode framing and stale offline state.
- Added one-command build/preflight, genuine ISO verifier, 16 regressions (33 total), native failure-resilience launch check and 60-second isolated process measurements.
- Attempted ISO/QEMU; blocked status remains explicit. No fake image or boot/RAM claim.

## Earlier checkpoint

- Continued the interrupted Python Core instead of restarting the project.
- Added native GTK dashboard, assistant, applications, history, memory, settings and search pages.
- Added provider/key editing with backend private-file persistence and profile probes.
- Fixed route-event construction and SQLite connection lifetime; corrected context fact overhead.
- Added fast active-response cancellation, regeneration context trimming and no-history nonpersistence.
- Kept network probes outside the Core state lock and UI work off the GTK main thread.
- Added Openbox/tint2/LightDM/user-service session, power/locking, and Debian live recipe.
- Added Core and native GTK fixtures, evidence, measurements and boot/hardware validation gates.
- No ISO or successful VM boot is claimed for this release.
