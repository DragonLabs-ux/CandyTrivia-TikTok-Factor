import os from 'node:os';

// Some isolated CI/container runtimes deny libuv's network-interface lookup.
// Remotion only uses this value to choose a local serving address, so a loopback
// fallback is sufficient. Normal Windows/macOS/Linux machines keep native data.
try {
  os.networkInterfaces();
} catch {
  os.networkInterfaces = () => ({
    lo: [{address: '127.0.0.1', netmask: '255.0.0.0', family: 'IPv4', mac: '00:00:00:00:00:00', internal: true, cidr: '127.0.0.1/8'}],
  });
}
