// Only the parent X page can connect. This frame exposes matching, not extension APIs.
window.addEventListener("message", function connect(event) {
  if (event.source !== parent || !["https://x.com", "https://twitter.com"].includes(event.origin)) return;
  if (event.data !== "hf:regex-connect" || event.ports.length !== 1) return;
  window.removeEventListener("message", connect);
  const port = event.ports[0];
  let worker;
  let queue = Promise.resolve();
  const blocked = new Set();

  function match(request) {
    const key = JSON.stringify([request.pattern, request.flags]);
    if (blocked.has(key)) return Promise.resolve({ matched: false, timedOut: true });
    return new Promise((resolve) => {
      let timer;
      let finished = false;
      function finish(result) {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        resolve(result);
      }
      function fail() {
        if (finished) return;
        if (worker) worker.terminate();
        worker = null;
        blocked.add(key);
        finish({ matched: false, timedOut: true });
      }
      function run() {
        // The deadline starts after worker startup, so cold startup isn't mistaken for a slow regex.
        clearTimeout(timer);
        timer = setTimeout(fail, 150);
        worker.onerror = fail;
        worker.onmessage = (event) => finish(event.data);
        worker.postMessage(request);
      }
      if (worker) run();
      else {
        try {
          worker = new Worker("regex-worker.js");
          worker.onerror = fail;
          timer = setTimeout(fail, 3000);
          worker.onmessage = run;
        } catch (_) {
          fail();
        }
      }
    });
  }

  port.onmessage = ({ data }) => {
    if (!data || typeof data.pattern !== "string" || typeof data.text !== "string") return;
    if (!["", "i"].includes(data.flags)) return;
    queue = queue.then(async () => {
      const result = await match(data);
      port.postMessage({ id: data.id, ...result });
    });
  };
  port.postMessage({ ready: true });
});
