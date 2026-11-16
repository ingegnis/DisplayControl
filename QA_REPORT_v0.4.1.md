> Historical report; see [TEST_REPORT.md](TEST_REPORT.md) for current release checks.

# QA — 0.4.1 Windows setup logic

2026-10-29; Linux x86_64, Python 3.13.5, installed FFmpeg. **39 tests passed** (15 existing + 24 setup tests), 7.845 s.

```sh
python -m unittest discover -s tests -v
python diagnose_ndi.py --seconds 0 --smoke-test
```

Checked exact encoder names, missing/process/timeout errors, real one-second black-video/silent-audio H.264/AAC fMP4 conversion (`avcC`, `mp4a`, `ftyp`), zero-source warnings, checksum/cache/mismatch handling, HTTPS-only redirects, safe ZIP extraction (traversal/case collisions/symlinks/size), staged replacement/rollback, relative paths, untouched data sentinels and selective dependency repair. The missing-FFmpeg/present-NDI case invoked only FFmpeg repair. Failed final checks did not report success.

Direct diagnosis found Python/FFmpeg/codec conversion working and official NDI absent; it correctly exited 1 without installing anything. No real NDI success was inferred.

Native Windows PowerShell, Authenticode, UAC, bootstrap and installers were reviewed but not executed in this historical Linux environment. Windows downloads/processes used mocks; HTTPS downloads were unavailable due to DNS. No Windows FFmpeg executable, real NDI, HX/H.265 or NEXCOM performance certification. UI behavior was unchanged. See [0.4 report](QA_REPORT_v0.4.md).
