# Technical references

References support protocol/API implementation; they are not loaded at runtime. No tutorial driver or proprietary SDK header/runtime is bundled. The ctypes binding uses interoperable ABI definitions. WebRTC/aiortc were evaluated but are not part of this release.

NDI references cover receive/frame ownership/reconnection, discovery/mDNS/Avahi, frame descriptors/stride/timestamps, dynamic loading, platform codecs and licensing. HX/H.265 discovery alone does not establish decoding support. FFmpeg HLS/fMP4 and MediaSource references cover browser delivery.

Windows setup references were consulted 2026-10-29; no supplier binaries are included. Downloads must pass current hash/signature checks. AKP03E references cross-check the public protocol; an external project's hardware testing does not certify this integration. Current USB identities, mappings and references: [CONTROLLERS.md](CONTROLLERS.md). Dependencies retain their original terms; no project license has been selected.

## References

- https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-recv
- https://docs.ndi.video/all/developing-with-ndi/sdk/ndi-find
- https://docs.ndi.video/all/developing-with-ndi/sdk/frame-types
- https://docs.ndi.video/all/developing-with-ndi/sdk/dynamic-loading-of-ndi-libraries
- https://docs.ndi.video/all/developing-with-ndi/sdk/platform-considerations
- https://docs.ndi.video/all/developing-with-ndi/sdk/licensing
- https://ndi.video/for-developers/ndi-sdk/
- https://docs.ndi.video/all/developing-with-ndi/advanced-sdk/using-h.264-h.265-and-aac-codecs/h.264-support
- https://ffmpeg.org/ffmpeg-formats.html#hls-2
- https://developer.mozilla.org/en-US/docs/Web/API/MediaSource
- https://www.gyan.dev/ffmpeg/builds/
- https://ffmpeg.org/download.html
- https://www.python.org/downloads/release/python-31410/
- https://docs.ndi.video/all/developing-with-ndi/sdk/software-distribution
- https://github.com/Aiacos/ajazz-control-center/blob/develop/docs/protocols/streamdeck/akp03.md
- https://github.com/tomekceszke/ajazz-akp03e
- https://github.com/mishamyrt/ajazz-sdk
- https://pypi.org/project/hidapi/
