# Next deployment checklist

- [x] `QC-e7t.1` [storage] Fix replay catalog duplicate-manifest refresh after stable run IDs
  Reviewed on `qc-storage`: local replay catalog refresh now tolerates duplicate manifests for one logical run and keeps the newest copy.

- [x] `QC-4xq` [storage] Stream local replay videos instead of loading whole MP4s into memory
  Reviewed on `qc-storage`: local replay now uses bounded chunked streaming for both range and non-range video responses.

- [x] `QC-hsn` [deploy] Confirm whether legacy or offline workstation rollout is required for the next deployment target
  Repo work for the legacy/offline path has been reviewed; remaining deployment risk is machine validation, not another branch fix.

- [?] `QC-7tf` [deploy] Validate the legacy runtime package only if the target machine requires it
  This stays conditional alongside `QC-hsn`; do not spend time here if the next deployment stays on the current modern workstation path.
