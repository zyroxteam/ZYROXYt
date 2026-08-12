// ZYROX Downloader frontend logic
(function () {
  "use strict";

  const urlInput = document.getElementById("url");
  const qualitySel = document.getElementById("quality");
  const fmtBtns = Array.from(document.querySelectorAll(".seg-btn"));
  const dlBtn = document.getElementById("dlBtn");
  const statusEl = document.getElementById("status");
  const resultEl = document.getElementById("result");
  const saveBtn = document.getElementById("saveBtn");
  const jsonBtn = document.getElementById("jsonBtn");
  const rBadge = document.getElementById("rBadge");
  const rName = document.getElementById("rName");
  const rMeta = document.getElementById("rMeta");
  const codeJson = document.getElementById("codeJson");
  const codeCurl = document.getElementById("codeCurl");

  const MP4_QUALITIES = ["144", "240", "360", "480", "720", "1080", "1440", "2160"];
  const MP3_QUALITIES = ["64", "128", "192", "256", "320"];

  let currentFmt = "mp4";
  let lastMeta = null;

  // Default sample code examples shown in docs
  codeJson.textContent =
    'curl "https://YOUR-APP.onrender.com/api/download?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720"';
  codeCurl.textContent =
    'curl -L "https://YOUR-APP.onrender.com/dl?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720" -o video.mp4';

  function fillQuality() {
    const list = currentFmt === "mp4" ? MP4_QUALITIES : MP3_QUALITIES;
    qualitySel.innerHTML = "";
    list.forEach((q) => {
      const o = document.createElement("option");
      o.value = q;
      o.textContent = currentFmt === "mp4" ? q + "p" : q + " kbps";
      if ((currentFmt === "mp4" && q === "720") || (currentFmt === "mp3" && q === "320")) {
        o.selected = true;
      }
      qualitySel.appendChild(o);
    });
  }

  function setFmt(fmt) {
    currentFmt = fmt;
    fmtBtns.forEach((b) => b.classList.toggle("active", b.dataset.fmt === fmt));
    fillQuality();
  }

  fmtBtns.forEach((b) => b.addEventListener("click", () => setFmt(b.dataset.fmt)));
  setFmt("mp4");

  function setStatus(msg, cls) {
    statusEl.textContent = msg;
    statusEl.className = "status" + (cls ? " " + cls : "");
  }

  function cleanName(name) {
    return (name || "download").replace(/[\\/:*?"<>|]/g, "_").replace(/\s+/g, " ").trim();
  }

  dlBtn.addEventListener("click", async () => {
    const url = urlInput.value.trim();
    if (!url) {
      setStatus("⚠ Please paste a YouTube link or video ID first.", "err");
      return;
    }

    dlBtn.disabled = true;
    setStatus("Preparing… contacting converter (can take a few seconds)…");
    resultEl.classList.add("hidden");

    const q = qualitySel.value;
    try {
      const res = await fetch(
        "/api/download?url=" + encodeURIComponent(url) +
        "&format=" + currentFmt + "&quality=" + q
      );
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || ("HTTP " + res.status));
      }

      lastMeta = data;
      rBadge.textContent = currentFmt.toUpperCase();
      rName.textContent = data.filename || "Download";
      rMeta.textContent =
        (currentFmt === "mp4" ? data.quality + "p · " : data.quality + " kbps · ") +
        "tunnel ready";
      // /dl now 302-redirects straight to the CDN -> fast, reliable download.
      saveBtn.href = "/dl?url=" + encodeURIComponent(url) +
        "&format=" + currentFmt + "&quality=" + q;
      saveBtn.setAttribute("download", cleanName(data.filename));
      resultEl.classList.remove("hidden");

      setStatus("✔ Ready. Click “Save file” to download directly from the CDN.", "ok");
    } catch (e) {
      setStatus("✖ " + e.message, "err");
    } finally {
      dlBtn.disabled = false;
    }
  });

  jsonBtn.addEventListener("click", () => {
    if (!lastMeta) return;
    const copy = {
      success: lastMeta.success,
      videoId: lastMeta.videoId,
      format: lastMeta.format,
      quality: lastMeta.quality,
      filename: lastMeta.filename,
      direct_url: lastMeta.direct_url,
      status: lastMeta.status,
    };
    navigator.clipboard.writeText(JSON.stringify(copy, null, 2))
      .then(() => setStatus("✔ JSON copied to clipboard.", "ok"))
      .catch(() => setStatus("Copy failed — select it manually.", "err"));
  });

  // Enter key in the URL box triggers download
  urlInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") dlBtn.click();
  });
})();
