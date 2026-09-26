"""Make the Godot web export fit Cloudflare Pages' 25 MiB per-file limit.

index.wasm (~38 MB) is stored gzip-compressed as index.wasm.gz (~9 MB) and the page unpacks it in the browser
with the built-in DecompressionStream, via a tiny fetch() wrapper injected into index.html.
Usage: python tools/web_postprocess.py export/web/game
"""
import gzip, os, sys, shutil

game = sys.argv[1]
wasm = os.path.join(game, "index.wasm")
with open(wasm, "rb") as src, gzip.open(wasm + ".gz", "wb", compresslevel=9) as dst:
    shutil.copyfileobj(src, dst)
os.remove(wasm)

SHIM = """<script>
// Cloudflare Pages caps files at 25 MiB: the engine ships as index.wasm.gz and is unpacked here.
(function () {
  const realFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    const url = typeof input === "string" ? input : input.url;
    if (/index\\.wasm(\\?|$)/.test(url)) {
      return realFetch(url.replace("index.wasm", "index.wasm.gz"), init).then(function (r) {
        if (!r.ok) return r;
        const body = r.body.pipeThrough(new DecompressionStream("gzip"));
        return new Response(body, { status: 200, headers: { "Content-Type": "application/wasm" } });
      });
    }
    return realFetch(input, init);
  };
})();
</script>
"""
html_path = os.path.join(game, "index.html")
html = open(html_path, encoding="utf-8").read()
if "index.wasm.gz" not in html:
    html = html.replace("<head>", "<head>\n" + SHIM, 1)
    open(html_path, "w", encoding="utf-8").write(html)
for f in sorted(os.listdir(game)):
    print(f"[WEB] {f:34s} {os.path.getsize(os.path.join(game, f)) / 1e6:6.2f} MB")
