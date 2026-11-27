---
title: RobinLab Watermark
emoji: 🖼️
colorFrom: gray
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# RobinLab watermark service

Downloads one image from the private bucket (read-only), stamps the RGS logo and
a faint tiled mark with Pillow, and returns it as an attachment. Nothing is
written to the bucket and nothing is stored.

Space secrets: `HF_TOKEN` (read-only token), `WATERMARK_KEY` (shared secret).

Local test without the network: `python watermark.py in.png out.png`
