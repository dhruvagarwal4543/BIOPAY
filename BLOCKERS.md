# Blockers
- Hardware (ESP32-S3 + fingerprint sensor): model/pins unknown. All physical verification BLOCKED.
- `.env` is guarded from being read in this session; backend tests ran with throwaway env values (local trust auth, db `postgres`).
