// Native JavaScript regex semantics, isolated so a slow match can be terminated.
self.onmessage = ({ data }) => {
  try {
    const matched = new RegExp(data.pattern, data.flags).test(data.text);
    self.postMessage({ matched });
  } catch (_) {
    self.postMessage({ matched: false });
  }
};
self.postMessage({ ready: true });
